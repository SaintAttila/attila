"""
Implements the Credential class, for password-based login credentials.
"""


import collections


from ..abc.configurations import Configurable
from ..abc.files import Path
from ..configurations import ConfigManager, INTERPOLATION_ESCAPE, INTERPOLATION_OPEN, \
    INTERPOLATION_CLOSE
from ..exceptions import verify_type
from ..plugins import config_loader
from . import encryption
from . import passwords


__author__ = 'Aaron Hosford'
__all__ = [
    'Credential',
]


@config_loader
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

        user, system_name = value.split('@')
        verify_type(user, str, non_empty=True)
        verify_type(system_name, str, non_empty=True)

        password = passwords.get_password(system_name, user)
        return cls(*args, user=user, password=password, **kwargs)

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
