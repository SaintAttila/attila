import collections
import configparser
import os

from . import encryption
from . import passwords


class Credential(collections.namedtuple('Credential', 'user password')):
    """
    A Credential is a user/password pair. It's handy for passing around to reduce the number of
    required parameters in function calls.
    """

    # These are here so PyCharm will notice the properties exist. It doesn't handle named tuples
    # perfectly.
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

        # There are two options for getting a password: Load it from the password database, or from
        # a locally-encrypted password file. If it's from the database, we need a system name. If
        # it's from a file, we need a file path.
        password = None
        if password_path or password_system_name:
            if password_path and os.path.isfile(password_path):
                with open(password_path, 'rb') as password_file:
                    password = encryption.locally_decrypt(password_file.read())

            if password is None:
                password = passwords.get_password(password_system_name, user)

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
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want
        # it, construct the string yourself.
        return 'password for user ' + str(self.user)

    def __repr__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want
        # it, construct the string yourself.
        return type(self).__name__ + "(" + repr(self.user) + ", '********')"
