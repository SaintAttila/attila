"""
attila.security
===============

Security- and credential-related functionality.

The security chain, summarized in one sentence:
    The various system account passwords used by our automation are stored in a
    database in encrypted form, using the master password, access to which is
    in turn protected using Windows' machine/login-local encryption, which
    relies on Windows authentication for the automation account login and
    Windows access rights to the server.

The master password to the DB is stored in a locally encrypted file using
Windows' built in CryptProtectData function. (For documentation, see
https://msdn.microsoft.com/en-us/library/aa380261.aspx.) This means that only
people who log in under the automation account can access the data, and they
also have to know what they're doing.

The master password is decrypted using CryptUnprotectData. (For documentation,
see https://msdn.microsoft.com/en-us/library/aa380882.aspx.) Remember, you must
be logged on with the automation Windows account, or the decryption will fail.

The master password is run through a cryptographic hashing algorithm to
generate an encryption key. It is this key that is passed to the cryptography
library to encode/decode automation passwords. This stage of encryption is
performed with a cryptographic encoding that depends on a shared key rather
than the local encryption mechanism that is used for the master password; as
long as you use the right password, you can use this from any machine with any
Windows login account.
"""


import base64
import collections
import configparser
import ctypes
import ctypes.wintypes
import getpass
import hashlib
import os


try:
    import win32con
    import win32security
except ImportError:
    win32con = None
    win32security = None


# For documentation on the cryptography library, or to download it, visit:
#   https://cryptography.io/en/latest/
# To install with pip:
#   pip install cryptography
import cryptography.fernet


import attila.adodb
import attila.env


# Make sure our DLLs are available up front. Think of these as similar to
# import statements, but for DLLs instead of Python modules.
kernel32 = ctypes.windll.kernel32
msvcrt = ctypes.cdll.msvcrt
crypt32 = ctypes.windll.crypt32


# See these URLs for information on the CRYPTPROTECT_* constants and the
# CryptProtectData and CryptUnprotectData OS system calls:
#   https://msdn.microsoft.com/en-us/library/aa380261.aspx
#   https://msdn.microsoft.com/en-us/library/aa380882.aspx

# Windows constants
CRYPTPROTECT_UI_FORBIDDEN = 1
CRYPTPROTECT_LOCAL_MACHINE = 4
CRYPTPROTECT_AUDIT = 16

# The size of the encryption salt used. See locally_encrypt() for an explanation.
SALT_SIZE = 1024


class Credential(collections.namedtuple('Credential', 'user password')):
    """
    A Credential is a user/password pair. It's handy for passing around to reduce the number of required parameters in
    function calls.
    """

    # These are here so PyCharm will notice the properties exist. It doesn't handle named tuples perfectly.
    user = None
    password = None

    @classmethod
    def load_from_config(cls, config, section):
        """
        Load a user name and password from a config section.

        :param config: A configparser.ConfigParser instance.
        :param section: The name of the section.
        :return: A Credential instance. The user and password may be strings or None.
        """

        assert isinstance(config, configparser.ConfigParser)

        config_section = config[section]

        user = config_section.get('User')
        password_path = config_section.get('Password Path')
        password_system_name = config_section.get('Password System Name')

        # There are two options for getting a password: Load it from the password database, or from a locally-
        # encrypted password file. If it's from the database, we need a system name. If it's from a file, we need a
        # file path.
        password = None
        if password_path or password_system_name:
            if password_path and os.path.isfile(password_path):
                with open(password_path, 'rb') as password_file:
                    password = locally_decrypt(password_file.read())

            if password is None:
                password = get_password(password_system_name, user)

        return cls(user, password)

    def __init__(self, user, password):
        super().__init__((user, password))

        assert user is None or (user and isinstance(user, str))
        assert password is None or (password and isinstance(password, str))

    def __bool__(self):
        return self.user is not None or self.password is not None

    @property
    def is_complete(self):
        """Whether both user and password were provided."""
        return self.user is not None and self.password is not None

    def __str__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want it, construct the
        # string yourself.
        return 'password for user ' + str(self.user)

    def __repr__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want it, construct the
        # string yourself.
        return type(self).__name__ + "(" + repr(self.user) + ", '********')"


# noinspection PyPep8Naming
class DATA_BLOB(ctypes.Structure):
    """
    This class is a wrapper for a C struct by the same name, from WINCRYPT.H. It is used to transfer byte sequences to/
    from the windows crypt32 DLL.

    The reason for using this class, together with the functions _to_blob, _from_blob, _crypt_protect_data, and
    _crypt_unprotect_data, rather than simply using win32crypt from the pywin32 package, is that pywin32 won't install
    on one of our servers, so anything dependent on it fails.
    """

    # cbData = length of pbData
    # pbData = c_buffer of length cbData, containing the actual data
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char))
    ]


def _to_blob(text):
    """
    Converts a Python string or bytes object to a data "blob" understood by the crypt32 windows DLL.

    :param text: The text to be converted to a data blob.
    :return: The data blob representing the text.
    """

    buffer = ctypes.c_buffer(text, len(text))
    return DATA_BLOB(len(text), buffer)


def _from_blob(blob):
    """
    Converts a data "blob" understood by the crypt32 windows DLL to a Python string or bytes object.

    :param blob: The data blob.
    :return: The text represented by the data blob.
    """

    length = int(blob.cbData)
    data_pointer = blob.pbData
    buffer = ctypes.c_buffer(length)
    msvcrt.memcpy(buffer, data_pointer, length)
    kernel32.LocalFree(data_pointer)
    return buffer.raw


def _crypt_protect_data(data, key=None, description=None, flags=None):
    """
    Wraps a call to the windows crypt32 DLL's CryptProtectData function. This function encrypts data with an optional
    password. If the default flags are used, it does so in such a way that it can only be decrypted on the same machine
    by the same user.

    :param data: The data to be encrypted.
    :param key: An optional additional encryption key.
    :param description: An optional description of the encrypted data.
    :param flags: The encryption flags. Defaults to CRYPTPROTECT_LOCAL_MACHINE | CRYPTPROTECT_UI_FORBIDDEN.
    :return: The encrypted data.
    """

    if flags is None:
        flags = CRYPTPROTECT_LOCAL_MACHINE | CRYPTPROTECT_UI_FORBIDDEN

    results = DATA_BLOB()

    success = crypt32.CryptProtectData(
        ctypes.byref(_to_blob(data)),
        description,
        ctypes.byref(_to_blob(key)) if key is not None else None,
        None,
        None,
        flags,
        ctypes.byref(results)
    )

    if not success:
        raise Exception("Encryption routine failed.")

    # noinspection PyTypeChecker
    return _from_blob(results)


def _crypt_unprotect_data(data, key=None, flags=None):
    """
    Wraps a call to the windows crypt32 DLL's CryptUnprotectData function. This function decrypts data previously
    encrypted by CryptProtectData.

    :param data: The data to be decrypted.
    :param key: The optional encryption key used to encrypt the data.
    :param flags: The decryption flags. Defaults to CRYPTPROTECT_UI_FORBIDDEN.
    :return: The decrypted data.
    """

    if flags is None:
        flags = CRYPTPROTECT_UI_FORBIDDEN

    results = DATA_BLOB()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(_to_blob(data)),
        None,
        ctypes.byref(_to_blob(key)) if key is not None else None,
        None,
        None,
        flags,
        ctypes.byref(results)
    )

    if not success:
        raise Exception("Decryption routine failed.")

    # noinspection PyTypeChecker
    return _from_blob(results)


def get_master_password_path():
    """
    Get the path to the locally encrypted master password file.

    :return: The master password file path.
    """
    return (
        attila.env.get_automation_config().get('Security', {}).get('Password Data Path') or
        attila.env.get_attila_config()['Security']['Password Data Path']
    )


def get_password_database():
    """
    Get the connection string to the password database.

    :return: The SQL connection info for the password database.
    :rtype: attila.adodb.ADODBConnectionInfo
    """
    section = attila.env.get_automation_config().get('Security', {}).get('Password Database')
    if section is None:
        raise KeyError("The Password Database parameter is not set in the automation config.")
    return attila.adodb.ADODBConnectionInfo.load_from_config(attila.env.get_automation_config(), section)


def get_user_account_hash(account_name=None):
    """
    Get the hash of a user account name. Defaults to current user account.

    :param account_name: The user name for the account. Defaults to current user.
    :return: An sha512 hash of the user account name, in hex digest format.
    """

    if account_name is None:
        account_name = getpass.getuser().upper()

    return hashlib.sha512(account_name.encode('utf-8')).hexdigest()


def to_bytes(data):
    """
    Ensure that a character sequence is represented as a bytes object. If it's already a bytes object, no change is
    made. If it's a string object, it's encoded as a UTF-8 string. Otherwise, it is treated as a sequence of character
    ordinal values.

    :param data: The data to be converted to bytes.
    :return: The data, converted to a bytes instance.
    """

    if isinstance(data, str):
        return data.encode('utf-8')
    else:
        return bytes(data)


def from_bytes(data):
    """
    Ensure that a character sequence is represented as a string object. If it's already a string object, no change is
    made. If it's a data object, it's decoded as a UTF-8 string. Otherwise, it is treated as a sequence of character
    ordinal values and decoded as a UTF-8 string.

    :param data: The data to be converted.
    :return: The data, converted to a str instance.
    """

    if isinstance(data, str):
        return data
    else:
        return bytes(data).decode('utf-8')


def locally_encrypt(data, key=None, description=None):
    """
    Calls the underlying OS system call function that performs encryption. Only the same user can decrypt the data
    encrypted by this function.

    :param data: The data to be encrypted.
    :param key: An optional additional encryption key.
    :param description: An optional description of the encrypted data.
    :return: The encrypted data.
    """

    if key:
        key = to_bytes(key)

    description = description or 'protected data'

    # Apply a salt to the data; depending on the encryption used, this can make
    # cracking it harder.
    salted_data = (
        os.urandom(SALT_SIZE) +
        to_bytes(data) +
        os.urandom(SALT_SIZE)
    )

    # CRYPTPROTECT_UI_FORBIDDEN indicates no user popups on failure.
    return _crypt_protect_data(
        salted_data,
        key,
        description,
        CRYPTPROTECT_LOCAL_MACHINE | CRYPTPROTECT_UI_FORBIDDEN
    )


def locally_decrypt(data, key=None):
    """
    Calls the underlying OS system call function that performs decryption. This function can only decrypt data encrypted
    by the same user using the locally_encrypt() function.

    :param data: The data to be decrypted.
    :param key: The optional additional key used to encrypt the data.
    :return: The decrypted data, as a str instance.
    """

    if key:
        key = to_bytes(key)

    salted_data = _crypt_unprotect_data(
        data,
        key,
        CRYPTPROTECT_UI_FORBIDDEN
    )

    # Remove the salt that was added by locally_encrypt(). (See locally_encrypt()
    # for an explanation.) Note that the result is a bytes instance, not a
    # string.
    return salted_data[SALT_SIZE:-SALT_SIZE]


def _set_master_password(password):
    """
    Encrypt and save the master automation password. (Note that this is distinct from the password for the Windows
    automation login.) The password must be a unicode string. IMPORTANT: Do not use this function directly; use
    set_master_password() instead. Otherwise the passwords encrypted in the database will not be accessible with the new
    master password.

    :param password: The new master password.
    """
    if not isinstance(password, str):
        raise TypeError(password)

    encrypted_password = locally_encrypt(password)
    del password

    with open(get_master_password_path(), 'wb') as file_obj:
        file_obj.write(encrypted_password)


def set_master_password(password):
    """
    Sets the master password. Re-encrypts each system password in the database that was encrypted with the old master
    password so that it is accessible with the new master password.

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
    Read and decrypt the master automation password. (Note that this is distinct from the password for the Windows
    automation login.) The password is returned as a unicode string. if refresh is set, first checks for a possible
    password update stored in the database.

    :param refresh: Whether to check the password database to see if the local cache is out of date.
    :return: The master password.
    """

    with open(get_master_password_path(), 'rb') as oFile:
        encrypted_password = oFile.read()

    password = from_bytes(locally_decrypt(encrypted_password))

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


def get_encryption_key(password):
    """
    Convert a password to a 32-bit encryption key, represented in base64 URL-safe encoding.

    :param password: The password to be encoded.
    :return: The encryption key for the given password.
    """
    return base64.b64encode(hashlib.sha256(to_bytes(password)).digest())


def encrypt(data, password=None):
    """
    Accept a string of unencrypted data and return it as an encrypted byte sequence (a bytes instance). If no password
    is provided, the master password is used by default. Note that this function returns a bytes instance, not a unicode
    string.

    :param data: The data to be encrypted.
    :param password: The password to use for encryption. Defaults to the master password.
    :return: The encrypted data.
    """

    key = get_encryption_key(password or get_master_password())
    del password
    symmetric_encoding = cryptography.fernet.Fernet(key)
    del key
    return symmetric_encoding.encrypt(to_bytes(data))


def decrypt(data, password=None):
    """
    Accept an encrypted byte sequence (a bytes instance) and return it as an unencrypted byte sequence. Note that the
    return value is a bytes instance, not a string; if you passed in a unicode string and want that back, you will have
    to decode it using from_bytes(). This is because this function makes no assumption that what you originally passed
    in was a UTF-8 string as opposed to a raw byte sequence.

    :param data: The data to be decrypted.
    :param password: The password to use for decryption. Defaults to the master password.
    :return: The decrypted data.
    """

    key = get_encryption_key(password or get_master_password())
    del password
    symmetric_encoding = cryptography.fernet.Fernet(key)
    del key

    # An error here typically indicates that a different password was used to
    # encrypt the data:
    return symmetric_encoding.decrypt(to_bytes(data))


def get_systems():
    """
    Get a set containing the systems for which username/password pairs have been stored.

    :return: A set containing the system names.
    """

    # Query the DB for the username.
    with attila.adodb.ADODBConnection(get_password_database()) as oConnection:
        results = oConnection.Execute(
            "SELECT DISTINCT System FROM AutomationPasswords"
        ).convert()
        return {row[0] for row in results}


def get_user_names(system_name, valid=True):
    """
    Get a set containing the user names for which a password has been stored for the given system. By default, only user
    names with valid passwords are returned. If valid is set to False, only user names with invalid passwords are
    returned. (This second option can be used for reporting purposes, to identify user names that need fresh passwords
    and notify the appropriate users.)

    :param system_name: The name of the system for which user names are requested.
    :param valid: Whether to only include user names with valid passwords.
    :return: The user names.
    """

    # Query the DB for the username.
    with attila.adodb.ADODBConnection(get_password_database()) as oConnection:
        results = oConnection.Execute(
            "SELECT UserName FROM AutomationPasswords WHERE System = '" +
            system_name + "' AND Valid = " + str(int(valid))
        ).convert()
        return {row[0] for row in results}


def set_password(system_name, user_name, password, valid=True, refresh_master=True):
    """
    Set the password for the given user name. If it already exists, overwrites it. If it doesn't exist, adds it.
    Automatically sets or clears the valid password flag based on the value passed in for valid.

    :param system_name: The name of the system.
    :param user_name: The user name on the system.
    :param password: The password for the user name.
    :param valid: Whether to set the valid flag in the database for this user name.
    :param refresh_master: Whether to refresh the master password in the process.
    """

    # I'm not really sure a salt is necessary here, but it won't hurt.
    salted_password = (
        os.urandom(SALT_SIZE) +
        to_bytes((password + ':').ljust(100)) +
        os.urandom(SALT_SIZE)
    )
    del password

    encrypted_password = encrypt(
        salted_password,
        get_master_password(refresh_master)
    )
    del salted_password

    encrypted_password = from_bytes(base64.b64encode(encrypted_password))

    # Write the username/password to the DB.
    with attila.adodb.ADODBConnection(get_password_database()) as connection:
        results = connection.Execute(
            "SELECT Password FROM AutomationPasswords WHERE System = '" +
            system_name + "' AND UserName = '" + user_name + "'"
        ).convert()

        if results:
            connection.Execute(
                "UPDATE AutomationPasswords SET Password = '" +
                encrypted_password + "', Valid = " + str(int(valid)) +
                " WHERE System = '" + system_name + "' AND UserName = '" +
                user_name + "'"
            )
        else:
            connection.Execute(
                "INSERT INTO AutomationPasswords VALUES('" + system_name + "', '" +
                user_name + "', '" + encrypted_password + "', " +
                str(int(valid)) + ")"
            )


def get_password(system, user_name, refresh_master=True):
    """
    Get the password for the given username. If no valid password entry exists for this username, an exception is
    raised.

    :param system: The name of the system to be logged into.
    :param user_name: The user name for which the password is needed.
    :param refresh_master: Whether to refresh the master password in the process.
    :return: The password for the user name.
    """

    # Query the DB for the username's password.
    with attila.adodb.ADODBConnection(get_password_database()) as connection:
        results = connection.Execute(
            "SELECT Password FROM AutomationPasswords WHERE System = '" +
            system + "' AND UserName = '" + user_name + "' AND Valid = 1"
        ).convert()
        for row in results:
            encrypted_password = base64.b64decode(row[0])
            break
        else:
            raise KeyError("No valid password entry for this user name.")

    # decrypt and remove salt & padding.
    # noinspection PyUnboundLocalVariable
    unsalted_password = decrypt(
        encrypted_password,
        get_master_password(refresh_master)
    )[SALT_SIZE:-SALT_SIZE]

    return from_bytes(unsalted_password).rstrip()[:-1]


def invalidate_password(system_name, user_name):
    """
    Mark the password for the given username as invalid. This should be called whenever a login attempt fails and
    repeated attempts with a bad password could result in account lockout.

    :param system_name: The name of the system.
    :param user_name: The user name on the system.
    """

    # Set the valid password flag to false in the DB.
    with attila.adodb.ADODBConnection(get_password_database()) as oConnection:
        oConnection.Execute(
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
    with attila.adodb.ADODBConnection(get_password_database()) as oConnection:
        oConnection.Execute(
            "DELETE FROM AutomationPasswords WHERE System = '" + system_name +
            "' AND UserName = '" + user_name + "'"
        )


class Impersonation:
    """
    This class allows a script to log in as another user temporarily. It works as a context manager, so the typical
    usage will look like this:

        with Impersonation(user_name, password):
            # Do stuff that requires us to be logged in as user_name

    If you want to stay logged in as another user for the duration of your function's execution, do this:

        impersonation = Impersonation(user_name, password)
        impersonation.impersonate()

    This will leave you impersonating user_name until "impersonation" goes out of scope and gets garbage-collected,
    or until you call impersonation.revert() or impersonation.logout().

    If you want to stay logged in until your script exits, without having to keep a reference to an Impersonation
    instance, do this:

        Impersonation.Sustained(user_name, password)
    """

    DEFAULT_USER = 'ERNAMAUTO'
    DEFAULT_DOMAIN = 'ERICSSON'
    PASSWORD_SYSTEM = 'Windows'
    USE_MASTER_PASSWORD = True

    _sustained = {}

    @classmethod
    def sustained(cls, user_name=None, password=None, domain=None):
        """
        Login as the given user (ERNAMAUTO by default) and leave it logged in.

        :param user_name: The account's user name.
        :param password: The account's password.
        :param domain: The account's domain.
        """

        if user_name is None:
            user_name = cls.DEFAULT_USER

        if domain is None:
            domain = cls.DEFAULT_DOMAIN

        key = (user_name, domain)

        if key not in cls._sustained:
            impersonation = cls(user_name, password, domain)
            impersonation.impersonate()
            cls._sustained[key] = impersonation

    def __init__(self, user_name=None, password=None, domain=None):
        self.handle = None

        if user_name is None:
            user_name = self.DEFAULT_USER

        if password is None:
            # noinspection PyBroadException
            try:
                password = get_password(self.PASSWORD_SYSTEM, user_name, False)
            except Exception:
                if user_name == self.DEFAULT_USER and self.USE_MASTER_PASSWORD:
                    password = get_master_password(False)
                else:
                    raise

        if domain is None:
            domain = self.DEFAULT_DOMAIN

        self.domain = domain
        self.user_name = user_name
        self.password = password

    def __del__(self):
        """
        Called automatically by the garbage collector just before the object is destroyed.
        """

        self.logout()

    def login(self):
        """
        Log in as the user. This just validates the credentials with the OS, but doesn't actually use them.
        """

        if self.handle is None:
            self.handle = win32security.LogonUser(
                self.user_name,
                self.domain,
                self.password,
                win32con.LOGON32_LOGON_INTERACTIVE,
                win32con.LOGON32_PROVIDER_DEFAULT
            )

    def logout(self):
        """
        Log out of the user's account. If currently impersonating the user, impersonation is also ended.
        """

        if self.handle is not None:
            win32security.RevertToSelf()
            self.handle.Close()
            self.handle = None

    def impersonate(self):
        """
        Begin using the credentials. Logs in first if necessary.
        """

        self.login()
        win32security.ImpersonateLoggedOnUser(self.handle)

    def revert(self):
        """
        Stop using the credentials. The user is left logged in, which can speed up later impersonations with the same
        credentials.
        """

        if self.handle is not None:
            win32security.RevertToSelf()

    def __enter__(self):
        """
        Called automatically upon entering a with block.
        """

        self.impersonate()

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Called automatically upon leaving a with block, whether due to normal execution or an error.
        """

        self.revert()
        return False  # Do not suppress errors


def main():
    """
    Updates the master password on the command line.
    """

    password = None

    try:
        password = getpass.getpass('Enter new master automation password: ')
        if password != getpass.getpass('Re-enter new master automation password: '):
            raise ValueError("Passwords do not match.")
        set_master_password(password)
    finally:
        del password

    print("Master automation password has been changed.")


if __name__ == '__main__':
    if not os.path.isfile(get_master_password_path()):
        main()
