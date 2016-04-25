"""
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


__author__ = 'Aaron Hosford'
__all__ = [
    'credentials',
    'encryption',
    'impersonation',
    'passwords',
]
