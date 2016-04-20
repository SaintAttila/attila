import base64
import getpass
import os

import cryptography.fernet

from .. import configurations
from ..abc.connections import Connector
from ..abc.files import Path
from ..exceptions import BadPasswordError, PasswordRequiredError
from . import encryption


def get_master_password_path():
    """
    Get the path to the locally encrypted master password file.

    :return: The master password file path.
    """

    auto_config = configurations.get_automation_config_loader()
    result = auto_config.load_option('Security', 'Password Data Path', Path, default=None)
    if result is not None:
        return result

    attila_config = configurations.get_attila_config_loader()
    return attila_config.load_option('Security', 'Password Data Path', Path)


def get_password_database_connector():
    """
    Get the connector to the password database.

    :return: The connector for the password database.
    :rtype: attila.abc.connections.Connector
    """
    config_loader = configurations.get_automation_config_loader()
    connector = config_loader.load_option('Security', 'Password Database Connector')
    assert isinstance(connector, Connector)
    return connector


def _set_master_password(password):
    """
    Encrypt and save the master automation password. (Note that this is distinct from the password
    for the Windows automation login.) The password must be a unicode string. IMPORTANT: Do not use
    this function directly; use set_master_password() instead. Otherwise the passwords encrypted in
    the database will not be accessible with the new master password.

    :param password: The new master password.
    """
    assert isinstance(password, str)
    if not password:
        raise BadPasswordError("Invalid password.")

    encrypted_password = encryption.locally_encrypt(password)
    del password

    with get_master_password_path().open(mode='wb') as password_file:
        password_file.write(encrypted_password)


def set_master_password(password):
    """
    Sets the master password. Re-encrypts each system password in the database that was encrypted
    with the old master password so that it is accessible with the new master password.

    :param password: The new master password.
    """

    if not os.path.exists(get_master_password_path()):
        _set_master_password(password)
        return

    old_master_password = get_master_password(False)
    if password == old_master_password:
        return  # Nothing to do...

    # encrypt the new password with the old one, so that other systems that
    # use the database can discover it.
    set_password(
        'MASTER',
        'MASTER',
        password,
        refresh_master=False
    )

    # Identify the system passwords that need to be re-encrypted
    passwords = []
    for system_name in get_systems():
        if system_name == 'MASTER':
            # Don't re-encrypt the new master password; it has to be encrypted
            # under the old master password so the other servers can update.
            continue

        for user_name in get_user_names(system_name):
            try:
                passwords.append(
                    (system_name, user_name, get_password(system_name, user_name, False))
                )
            except cryptography.fernet.InvalidToken:
                # If it can't be decrypted, odds are we already changed the
                # master password on another agent or server. But even if that's
                # not the case, there's nothing we can do until the password
                # is set again using the new master password.
                pass

    # Set the new master password
    _set_master_password(password)

    # Re-encrypt the system passwords and write them back to the table
    while passwords:
        system_name, user_name, password = passwords.pop()
        set_password(system_name, user_name, password, refresh_master=False)
        del password


def get_master_password(refresh=True):
    """
    Read and decrypt the master automation password. (Note that this is distinct from the password
    for the Windows automation login.) The password is returned as a unicode string. if refresh is
    set, first checks for a possible password update stored in the database.

    :param refresh: Whether to check the password database to see if the local cache is out of date.
    :return: The master password.
    """

    with get_master_password_path().open(mode='rb') as password_file:
        encrypted_password = password_file.read()

    password = encryption.from_bytes(encryption.locally_decrypt(encrypted_password))

    if not refresh:
        return password

    # noinspection PyBroadException
    try:
        new_password = get_password('MASTER', 'MASTER', False)
    except Exception:
        return password
    else:
        _set_master_password(new_password)
        return new_password


def get_systems():
    """
    Get a set containing the systems for which username/password pairs have been stored.

    :return: A set containing the system names.
    """

    # Query the DB for the username.
    with get_password_database_connector().connect() as connection:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        results = connection.Execute("SELECT DISTINCT System FROM AutomationPasswords")
        return {row[0] for row in results}


def get_user_names(system_name, valid=True):
    """
    Get a set containing the user names for which a password has been stored for the given system.
    By default, only user names with valid passwords are returned. If valid is set to False, only
    user names with invalid passwords are returned. (This second option can be used for reporting
    purposes, to identify user names that need fresh passwords and notify the appropriate users.)

    :param system_name: The name of the system for which user names are requested.
    :param valid: Whether to only include user names with valid passwords.
    :return: The user names.
    """

    # Query the DB for the username.
    with get_password_database_connector().connect() as connection:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        results = connection.Execute(
            "SELECT UserName FROM AutomationPasswords WHERE System = '" +
            system_name + "' AND Valid = " + str(int(valid))
        )
        return {row[0] for row in results}


def set_password(system_name, user_name, password, valid=True, refresh_master=True):
    """
    Set the password for the given user name. If it already exists, overwrites it. If it doesn't
    exist, adds it. Automatically sets or clears the valid password flag based on the value passed
    in for valid.

    :param system_name: The name of the system.
    :param user_name: The user name on the system.
    :param password: The password for the user name.
    :param valid: Whether to set the valid flag in the database for this user name.
    :param refresh_master: Whether to refresh the master password in the process.
    """

    # I'm not really sure a salt is necessary here, but it won't hurt.
    salted_password = (
        os.urandom(encryption.SALT_SIZE) +
        encryption.to_bytes((password + ':').ljust(100)) +
        os.urandom(encryption.SALT_SIZE)
    )
    del password

    encrypted_password = encryption.encrypt(
        salted_password,
        get_master_password(refresh_master)
    )
    del salted_password

    encrypted_password = encryption.from_bytes(base64.b64encode(encrypted_password))

    # Write the username/password to the DB.
    with get_password_database_connector().connect() as connection:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        results = list(
            connection.Execute(
                "SELECT Password FROM AutomationPasswords WHERE System = '" +
                system_name + "' AND UserName = '" + user_name + "'"
            )
        )

        if results:
            # noinspection SqlDialectInspection,SqlNoDataSourceInspection
            connection.Execute(
                "UPDATE AutomationPasswords SET Password = '" +
                encrypted_password + "', Valid = " + str(int(valid)) +
                " WHERE System = '" + system_name + "' AND UserName = '" +
                user_name + "'"
            )
        else:
            # noinspection SqlDialectInspection,SqlNoDataSourceInspection
            connection.Execute(
                "INSERT INTO AutomationPasswords VALUES('" + system_name + "', '" +
                user_name + "', '" + encrypted_password + "', " +
                str(int(valid)) + ")"
            )


def get_password(system, user_name, refresh_master=True):
    """
    Get the password for the given username. If no valid password entry exists for this username, an
    exception is raised.

    :param system: The name of the system to be logged into.
    :param user_name: The user name for which the password is needed.
    :param refresh_master: Whether to refresh the master password in the process.
    :return: The password for the user name.
    """

    # Query the DB for the username's password.
    with get_password_database_connector().connect() as connection:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        results = connection.Execute(
            "SELECT Password FROM AutomationPasswords WHERE System = '" +
            system + "' AND UserName = '" + user_name + "' AND Valid = 1"
        )
        for row in results:
            encrypted_password = base64.b64decode(row[0])
            break
        else:
            raise PasswordRequiredError("No valid password entry for this user name.")

    # decrypt and remove salt & padding.
    # noinspection PyUnboundLocalVariable
    unsalted_password = encryption.decrypt(
        encrypted_password,
        get_master_password(refresh_master)
    )[encryption.SALT_SIZE:-encryption.SALT_SIZE]

    return encryption.from_bytes(unsalted_password).rstrip()[:-1]


def invalidate_password(system_name, user_name):
    """
    Mark the password for the given username as invalid. This should be called whenever a login
    attempt fails and repeated attempts with a bad password could result in account lockout.

    :param system_name: The name of the system.
    :param user_name: The user name on the system.
    """

    # Set the valid password flag to false in the DB.
    with get_password_database_connector().connect() as connection:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        connection.Execute(
            "UPDATE AutomationPasswords SET Valid = 0 WHERE System = '" +
            system_name + "' AND UserName = '" + user_name + "'"
        )


def remove_user_name(system_name, user_name):
    """
    Remove the username/password pair from the database.

    :param system_name: The name of the system.
    :param user_name: The user name on the system.
    """

    # Delete the username/password from the DB.
    with get_password_database_connector().connect() as connection:
        # noinspection SqlDialectInspection,SqlNoDataSourceInspection
        connection.Execute(
            "DELETE FROM AutomationPasswords WHERE System = '" + system_name +
            "' AND UserName = '" + user_name + "'"
        )


def main():
    """
    Updates the master password on the command line.
    """

    password = None

    try:
        password = getpass.getpass('Enter new master automation password: ')
        if password != getpass.getpass('Re-enter new master automation password: '):
            raise BadPasswordError("Passwords do not match.")
        set_master_password(password)
    finally:
        del password

    print("Master automation password has been changed.")


if __name__ == '__main__':
    main()
