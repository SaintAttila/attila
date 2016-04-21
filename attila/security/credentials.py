"""
attila.security.credentials
===========================

Implements the Credential class, for password-based login credentials.
"""


import collections


from ..abc.configurations import Configurable
from ..abc.files import Path

from ..configurations import ConfigLoader
from ..exceptions import verify_type

from . import encryption
from . import passwords


class Credential(collections.namedtuple('Credential', 'user password domain'), Configurable):
    """
    A Credential is a user/password pair. It's handy for passing around to reduce the number of
    required parameters in function calls.
    """

    # These are here so PyCharm will notice the properties exist. It doesn't handle named tuples
    # perfectly.
    user = None
    password = None
    domain = None

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        verify_type(config_loader, ConfigLoader)
        assert isinstance(config_loader, ConfigLoader)
        verify_type(value, str, non_empty=True)

        user, system_name = value.split('@')
        verify_type(user, str, non_empty=True)
        verify_type(system_name, str, non_empty=True)

        password = passwords.get_password(system_name, user)
        return cls(*args, user=user, password=password, **kwargs)

    @classmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(config_loader, ConfigLoader)
        assert isinstance(config_loader, ConfigLoader)
        verify_type(section, str, non_empty=True)

        user = config_loader.load_option(section, 'User')

        # There are two options for getting a password: Load it from the password database, or from
        # a locally-encrypted password file. If it's from the database, we need a system name. If
        # it's from a file, we need a file path.
        if config_loader.has_option(section, 'Password Path'):
            path = config_loader.load_option(section, 'Password Path', Path)
            with path.open(mode='rb') as password_file:
                password = encryption.locally_decrypt(password_file.read())
        else:
            system_name = config_loader.load_option(section, 'System Name', str)
            password = passwords.get_password(system_name, user)

        return cls(*args, user=user, password=password, **kwargs)

    def __init__(self, user, password, domain):
        super().__init__((user, password, domain))

        assert user is None or (user and isinstance(user, str))
        assert password is None or (password and isinstance(password, str))
        assert domain is None or (domain and isinstance(domain, str))

    def __bool__(self):
        return self.user is not None or self.password is not None

    @property
    def is_complete(self):
        """Whether all required elements were provided."""
        return self.user is not None and self.password is not None and self.domain is not None

    def __str__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want
        # it, construct the string yourself.
        return 'password for user ' + str(self.user) + ' on domain ' + str(self.domain)

    def __repr__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want
        # it, construct the string yourself.
        return \
            type(self).__name__ + "(" + repr(self.user) + ", '********', " + repr(self.domain) + ")"
