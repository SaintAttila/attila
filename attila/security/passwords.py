"""
Password storage and retrieval.
"""

# TODO: The SQL queries refer to a System column, but it should be named Domain.
#       Unfortunately, we already have a database that uses System as the name,
#       and changing the queries would break our setup. How do we fix this so it
#       works universally? Something in the config files?


# TODO: Make the table name, field names, and salt size configurable.

# TODO: Make the get_password function check for locally encrypted passwords first, 
#       before attempting to query the database. Add an option to the set_password
#       function to allow the user to control whether the password is set locally 
#       or in the database.


import base64
import getpass
import os


import cryptography.fernet


from sql_dialects import T, F, V


from ..abc.sql import SQLConnector, sql_connection
from ..abc.files import Path
from ..exceptions import BadPasswordError, PasswordRequiredError
from .. import configurations
from . import encryption


__author__ = 'Aaron Hosford'
__all__ = [
    'get_master_password_path',
    'get_password_database_connector',
    'set_master_password',
    'get_master_password',
    'get_domains',
    'get_users',
    'set_password',
    'get_password',
    'invalidate_password',
    'remove_user',
    'main',
]


def get_master_password_path():
    """
    Get the path to the locally encrypted master password file.

    :return: The master password file path.
    """

    auto_config = configurations.get_automation_config_manager()
    result = auto_config.load_option('Security', 'Master Password Path', Path, default=None)
    if result is not None:
        return result

    attila_config = configurations.get_attila_config_manager()
    return attila_config.load_option('Security', 'Master Password Path', Path)


def get_password_database_connector():
    """
    Get the connector to the password database.

    :return: The connector for the password database.
    :rtype: attila.abc.sql.SQLConnector
    """
    config_loader = configurations.get_automation_config_manager()
    connector = config_loader.load_option('Security', 'Password DB Connector')
    assert isinstance(connector, SQLConnector)
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
    Sets the master password. Re-encrypts each domain password in the database that was encrypted
    with the old master password so that it is accessible with the new master password.

    :param password: The new master password.
    """

    if not get_master_password_path().exists:
        _set_master_password(password)
        return

    old_master_password = get_master_password(False)
    if password == old_master_password:
        return  # Nothing to do...

    # Encrypt the new password with the old one, so that other systems that use the database can
    # discover it.
    set_password(
        'MASTER',
        'MASTER',
        password,
        refresh_master=False
    )

    # Identify the domain passwords that need to be re-encrypted
    passwords = []
    for domain in get_domains():
        if domain == 'MASTER':
            # Don't re-encrypt the new master password; it has to be encrypted
            # under the old master password so the other servers can update.
            continue

        for user in get_users(domain):
            try:
                passwords.append(
                    (domain, user, get_password(domain, user, False))
                )
            except cryptography.fernet.InvalidToken:
                # If it can't be decrypted, odds are we already changed the
                # master password on another agent or server. But even if that's
                # not the case, there's nothing we can do until the password
                # is set again using the new master password.
                pass

    # Set the new master password
    _set_master_password(password)

    # Re-encrypt the domain passwords and write them back to the table
    while passwords:
        domain, user, password = passwords.pop()
        set_password(domain, user, password, refresh_master=False)
        del password


def get_master_password(refresh=True, update=True):
    """
    Read and decrypt the master automation password. (Note that this is distinct from the password
    for the Windows automation login.) The password is returned as a unicode string. if refresh is
    set, first checks for a possible password update stored in the database.

    :param refresh: Whether to check the password database to see if the local cache is out of date.
    :param update: Whether to ask the user to update if the password file is missing.
    :return: The master password.
    """

    path = get_master_password_path()
    assert isinstance(path, Path)

    if update and not path.exists:
        update_master_password()

    path.verify_is_file()

    with path.open(mode='rb') as password_file:
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


def get_domains():
    """
    Get a set containing the domains for which username/password pairs have been stored.

    :return: A set containing the domain names.
    """

    # "SELECT DISTINCT System FROM AutomationPasswords"
    query = T.AutomationPasswords.select(F.System).distinct()

    # Query the DB for the username.
    with get_password_database_connector().connect() as connection:
        assert isinstance(connection, sql_connection)
        results = connection.execute(query)
        return {row[0] for row in results}


def get_users(domain, valid=True):
    """
    Get a set containing the user names for which a password has been stored for the given domain.
    By default, only user names with valid passwords are returned. If valid is set to False, only
    user names with invalid passwords are returned. (This second option can be used for reporting
    purposes, to identify user names that need fresh passwords and notify the appropriate users.)

    :param domain: The name of the login domain.
    :param valid: Whether to only include user names with valid passwords.
    :return: The user names.
    """

    # "SELECT UserName FROM AutomationPasswords WHERE System = '" +
    # domain + "' AND Valid = " + str(int(valid))
    query = T.AutomationPasswords.select(F.UserName).where(
        (F.System == V(domain)) &
        (F.Valid == V(valid))
    )

    # Query the DB for the username.
    with get_password_database_connector().connect() as connection:
        assert isinstance(connection, sql_connection)
        results = connection.execute(query)
        return {row[0] for row in results}


def set_password(domain, user, password, valid=True, refresh_master=True):
    """
    Set the password for the given user name. If it already exists, overwrites it. If it doesn't
    exist, adds it. Automatically sets or clears the valid password flag based on the value passed
    in for valid.

    :param domain: The name of the domain.
    :param user: The user name on the domain.
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

    # "SELECT Password FROM AutomationPasswords WHERE System = '" +
    # domain + "' AND UserName = '" + user + "'"
    list_query = T.AutomationPasswords.select(F.Password).where(
        (F.System == V(domain)) &
        (F.UserName == V(user))
    )

    # "UPDATE AutomationPasswords SET Password = '" +
    # encrypted_password + "', Valid = " + str(int(valid)) +
    # " WHERE System = '" + domain + "' AND UserName = '" +
    # user + "'"
    update_query = T.AutomationPasswords.update().\
        set(F.Password, V(encrypted_password)).\
        set(F.Valid, V(valid)).\
        where(
            (F.System == V(domain)) &
            (F.UserName == V(user))
        )

    # "INSERT INTO AutomationPasswords VALUES('" + domain + "', '" +
    # user + "', '" + encrypted_password + "', " +
    # str(int(valid)) + ")"
    insert_query = T.AutomationPasswords.insert().\
        set(F.System, V(domain)).\
        set(F.UserName, V(user)).\
        set(F.Password, V(encrypted_password)).\
        set(F.Valid, V(valid))

    # Write the username/password to the DB.
    with get_password_database_connector().connect() as connection:
        assert isinstance(connection, sql_connection)
        if list(connection.execute(list_query)):
            connection.execute(update_query)
        else:
            connection.execute(insert_query)


def get_password(domain, user, refresh_master=True):
    """
    Get the password for the given username. If no valid password entry exists for this username, an
    exception is raised.

    :param domain: The name of the domain to be logged into.
    :param user: The user name for which the password is needed.
    :param refresh_master: Whether to refresh the master password in the process.
    :return: The password for the user name.
    """

    # "SELECT Password FROM AutomationPasswords WHERE System = '" +
    # domain + "' AND UserName = '" + user + "' AND Valid = 1"
    query = T.AutomationPasswords.select(F.Password).where(
        (F.System == V(domain)) &
        (F.UserName == V(user)) &
        (F.Valid == V(True))
    )

    # Query the DB for the username's password.
    with get_password_database_connector().connect() as connection:
        results = connection.execute(query)
        for row in results:
            encrypted_password = base64.b64decode(row[0])
            break
        else:
            raise PasswordRequiredError("No valid password entry for %s@%s." % (user, domain))

    # decrypt and remove salt & padding.
    # noinspection PyUnboundLocalVariable
    unsalted_password = encryption.decrypt(
        encrypted_password,
        get_master_password(refresh_master)
    )[encryption.SALT_SIZE:-encryption.SALT_SIZE]

    return encryption.from_bytes(unsalted_password).rstrip()[:-1]


def invalidate_password(domain, user):
    """
    Mark the password for the given username as invalid. This should be called whenever a login
    attempt fails and repeated attempts with a bad password could result in account lockout.

    :param domain: The name of the domain.
    :param user: The user name on the domain.
    """

    # "UPDATE AutomationPasswords SET Valid = 0 WHERE System = '" +
    # domain + "' AND UserName = '" + user + "'"
    query = T.AutomationPasswords.update().set(F.Valid, V(False)).where(
        (F.System == V(domain)) &
        (F.UserName == V(user))
    )

    # Set the valid password flag to false in the DB.
    with get_password_database_connector().connect() as connection:
        assert isinstance(connection, sql_connection)
        connection.execute(query)


def remove_user(domain, user):
    """
    Remove the username/password pair from the database.

    :param domain: The name of the domain.
    :param user: The user name on the domain.
    """

    # "DELETE FROM AutomationPasswords WHERE System = '" + domain +
    # "' AND UserName = '" + user + "'"
    query = T.AutomationPasswords.delete().where(
        (F.System == V(domain)) &
        (F.UserName == V(user))
    )

    # Delete the username/password from the DB.
    with get_password_database_connector().connect() as connection:
        assert isinstance(connection, sql_connection)
        connection.execute(query)


def update_master_password():
    """
    Updates the master password.

    :return:
    """
    password = getpass.getpass('Enter new master automation password: ')
    if password != getpass.getpass('Re-enter new master automation password: '):
        raise BadPasswordError("Passwords do not match.")
    set_master_password(password)


def main():
    """
    Updates the master password on the command line.
    """

    update_master_password()
    print("Master automation password has been changed.")


if __name__ == '__main__':
    main()
