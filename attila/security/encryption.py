"""
attila.security.encryption
==========================

Standardized encryption routines.
"""


import base64
import ctypes
import ctypes.wintypes
import hashlib
import os


# For documentation on the cryptography library, or to download it, visit:
#   https://cryptography.io/en/latest/
# To install with pip:
#   pip install cryptography
import cryptography.fernet

from . import passwords
from ..exceptions import EncryptionError, DecryptionError


# Make sure our DLLs are available up front. Think of these as similar to
# import statements, but for DLLs instead of Python modules.
kernel32 = ctypes.windll.kernel32
msvcrt = ctypes.cdll.msvcrt
crypt32 = ctypes.windll.crypt32


__author__ = 'Aaron Hosford'
__all__ = [
    'to_bytes',
    'from_bytes',
    'get_encryption_key',
    'locally_encrypt',
    'locally_decrypt',
    'encrypt',
    'decrypt',
]


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


# noinspection PyPep8Naming
class DATA_BLOB(ctypes.Structure):
    """
    This class is a wrapper for a C struct by the same name, from WINCRYPT.H. It is used to transfer
    byte sequences to/from the windows crypt32 DLL.

    The reason for using this class, together with the functions _to_blob, _from_blob,
    _crypt_protect_data, and _crypt_unprotect_data, rather than simply using win32crypt from the
    pywin32 package, is that pywin32 won't install on one of our servers, so anything dependent on
    it fails.
    """

    # cbData is the length of pbData
    # pbData is a c_buffer of length cbData, containing the actual data
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
    Wraps a call to the windows crypt32 DLL's CryptProtectData function. This function encrypts data
    with an optional password. If the default flags are used, it does so in such a way that it can
    only be decrypted on the same machine by the same user.

    :param data: The data to be encrypted.
    :param key: An optional additional encryption key.
    :param description: An optional description of the encrypted data.
    :param flags: The encryption flags. Defaults to CRYPTPROTECT_LOCAL_MACHINE |
        CRYPTPROTECT_UI_FORBIDDEN.
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
        raise EncryptionError("Encryption routine failed.")

    # noinspection PyTypeChecker
    return _from_blob(results)


def _crypt_unprotect_data(data, key=None, flags=None):
    """
    Wraps a call to the windows crypt32 DLL's CryptUnprotectData function. This function decrypts
    data previously encrypted by CryptProtectData.

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
        raise DecryptionError("Decryption routine failed.")

    # noinspection PyTypeChecker
    return _from_blob(results)


def to_bytes(data):
    """
    Ensure that a character sequence is represented as a bytes object. If it's already a bytes
    object, no change is made. If it's a string object, it's encoded as a UTF-8 string. Otherwise,
    it is treated as a sequence of character ordinal values.

    :param data: The data to be converted to bytes.
    :return: The data, converted to a bytes instance.
    """

    if isinstance(data, str):
        return data.encode()
    else:
        return bytes(data)


def from_bytes(data):
    """
    Ensure that a character sequence is represented as a string object. If it's already a string
    object, no change is made. If it's a data object, it's decoded as a UTF-8 string. Otherwise, it
    is treated as a sequence of character ordinal values and decoded as a UTF-8 string.

    :param data: The data to be converted.
    :return: The data, converted to a str instance.
    """

    if isinstance(data, str):
        return data
    else:
        return bytes(data).decode()


def get_encryption_key(password):
    """
    Convert a password to a 32-bit encryption key, represented in base64 URL-safe encoding.

    :param password: The password to be encoded.
    :return: The encryption key for the given password.
    """
    return base64.b64encode(hashlib.sha256(to_bytes(password)).digest())


def locally_encrypt(data, key=None, description=None):
    """
    Calls the underlying OS system call function that performs encryption. Only the same user can
    decrypt the data encrypted by this function.

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
    Calls the underlying OS system call function that performs decryption. This function can only
    decrypt data encrypted by the same user using the locally_encrypt() function.

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


def encrypt(data, password=None):
    """
    Accept a string of unencrypted data and return it as an encrypted byte sequence (a bytes
    instance). If no password is provided, the master password is used by default. Note that this
    function returns a bytes instance, not a unicode string.

    :param data: The data to be encrypted.
    :param password: The password to use for encryption. Defaults to the master password.
    :return: The encrypted data.
    """

    key = get_encryption_key(password or passwords.get_master_password())
    del password
    symmetric_encoding = cryptography.fernet.Fernet(key)
    del key
    return symmetric_encoding.encrypt(to_bytes(data))


def decrypt(data, password=None):
    """
    Accept an encrypted byte sequence (a bytes instance) and return it as an unencrypted byte
    sequence. Note that the return value is a bytes instance, not a string; if you passed in a
    unicode string and want that back, you will have to decode it using from_bytes(). This is
    because this function makes no assumption that what you originally passed in was a UTF-8 string
    as opposed to a raw byte sequence.

    :param data: The data to be decrypted.
    :param password: The password to use for decryption. Defaults to the master password.
    :return: The decrypted data.
    """

    key = get_encryption_key(password or passwords.get_master_password())
    del password
    symmetric_encoding = cryptography.fernet.Fernet(key)
    del key

    # An error here typically indicates that a different password was used to
    # encrypt the data:
    return symmetric_encoding.decrypt(to_bytes(data))
