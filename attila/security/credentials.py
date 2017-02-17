"""
Implements the Credential class, for password-based login credentials.
"""


import collections


from ..abc.configurations import Configurable
from ..abc.files import Path
from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader
from . import encryption, passwords


__author__ = 'Aaron Hosford'
__all__ = [
    'Credential',
]


@config_loader
class Credential(Configurable):
    """
    A Credential is a user/password pair. It's handy for passing around to reduce the number of
    required parameters in function calls.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)
        verify_type(value, str, non_empty=True)

        user, domain = value.split('@')
        verify_type(user, str, non_empty=True)
        verify_type(domain, str, non_empty=True)

        password = passwords.get_password(domain, user)
        return cls(*args, user=user, password=password, domain=domain, **kwargs)

    @classmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)
        verify_type(section, str, non_empty=True)

        user = manager.load_option(section, 'user')
        domain = manager.load_option(section, 'domain')

        # There are two options for getting a password: Load it from the password database, or from
        # a locally-encrypted password file. If it's from the database, we need a system name. If
        # it's from a file, we need a file path.
        if manager.has_option(section, 'password path'):
            path = manager.load_option(section, 'password path', Path)
            if path == passwords.get_master_password_path():
                password = passwords.get_master_password(refresh=False)
            else:
                with path.open(mode='rb') as password_file:
                    password = encryption.locally_decrypt(password_file.read()).decode('utf-8')
        else:
            password = passwords.get_password(domain, user)

        return cls(*args, user=user, password=password, domain=domain, **kwargs)

    def __init__(self, user, password, domain):
        super().__init__()

        assert user is None or (user and isinstance(user, str))
        assert not password or isinstance(password, str)
        assert domain is None or (domain and isinstance(domain, str))

        self._user = user
        self._password = password or None
        self._domain = domain

    def __bool__(self):
        return self.user is not None or self.password is not None

    @property
    def is_complete(self):
        """Whether all required elements were provided."""
        return self.user is not None and self.password is not None and self.domain is not None

    @property
    def user(self):
        return self._user

    @property
    def password(self):
        return self._password

    @property
    def domain(self):
        return self._domain

    def __str__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want
        # it, construct the string yourself.
        return 'password for user ' + str(self.user) + ' on domain ' + str(self.domain)

    def __repr__(self):
        # We hide the password on purpose, to prevent accidentally displaying it. If you really want
        # it, construct the string yourself.
        return type(self).__name__ + "(" + repr(self.user) + ", '********', " + repr(self.domain) + ")"

    def __eq__(self, other):
        if not isinstance(other, Credential):
            return NotImplemented
        return self._user == other._user and self._password == other._password and self._domain == other._domain

    def __ne__(self, other):
        if not isinstance(other, Credential):
            return NotImplemented
        return not (self._user == other._user and self._password == other._password and self._domain == other._domain)

    def __hash__(self):
        return hash((self._user, self._password, self._domain))

    def __iter__(self):
        yield self._user
        yield self._password
        yield self._domain

    def __len__(self):
        return 3

    def __getitem__(self, item):
        return (self._user, self._password, self._domain)[item]
