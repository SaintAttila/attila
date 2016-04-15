"""
attila.abc.configurables
========================

Interface definition for configurable objects.
"""

from abc import ABCMeta, abstractmethod


# noinspection PyUnresolvedReferences
from ..exceptions import ConfigurationError, InvalidConfigurationError, ConfigSectionNotFoundError, \
    ObjectNotConfiguredError, ConfigParameterNotFoundError, ObjectNotReconfigurableError, \
    NoConfigurableInstanceTypeError, verify_type


__all__ = [
    "Configurable",
    "ConfigurationError",
    "InvalidConfigurationError",
    "ConfigSectionNotFoundError",
    "ConfigParameterNotFoundError",
    "ObjectNotConfiguredError",
    "ObjectNotReconfigurableError",
    "NoConfigurableInstanceTypeError",
]


# class Configuration(metaclass=ABCMeta):
#     """
#     The Configuration class is an abstract base class for configuration objects.
#     """
#
#     @classmethod
#     def load_instance(cls, config, section):
#         """
#         Create a new instance of this class, based on the contents of a section loaded from a config file.
#
#         :param config: A configparser.ConfigParser instance.
#         :param section: The name of the section the object should be configured from.
#         :return: A new configuration instance.
#         """
#         verify_type(config, configparser.ConfigParser)
#         verify_type(section, str, non_empty=True)
#         return cls()
#
#     @property
#     def connection_type(self):
#         """The instance type that accepts this configuration, or None if instances are not supported."""
#         return None
#
#     @abstractmethod
#     def copy(self):
#         """
#         Create a copy of this configuration.
#
#         :return: A new Configuration instance.
#         """
#         raise NotImplementedError()
#
#     @property
#     def is_valid(self):
#         """Whether the configuration is valid."""
#         return True  # By default, always valid.
#
#     def validate(self):
#         """
#         Verify that the configuration is consistent. If not, raise an exception.
#         """
#         if not self.is_valid:
#             raise InvalidConfigurationError("The configuration is invalid.")
#
#     def extend(self, *args, **kwargs):
#         """
#         Extend the configuration with additional information.
#
#         :return: A new configuration with the additional information incorporated into it.
#         """
#         if args or kwargs:
#             raise OperationNotSupportedError("The configuration cannot be extended.")
#         return self
#
#     def new_instance(self, *args, **kwargs):
#         """
#         Create a newly configured instance and return it.
#
#         :return: A new Configurable instance.
#         """
#         extended_configuration = self.extend(*args, **kwargs)
#         connection_type = extended_configuration.connection_type
#         if connection_type is None:
#             raise NoConfigurableInstanceTypeError("This configuration does not support configured instances.")
#         else:
#             assert callable(connection_type)
#             return connection_type(extended_configuration)
#
#
# class Configurable(metaclass=ABCMeta):
#     """
#     The Configurable class is an abstract base class for configurable objects.
#     """
#
#     @classmethod
#     def get_configuration_type(cls):
#         """
#         Return the configuration base type associated with this configurable type.
#
#         :return: A Configuration subclass.
#         """
#         return Configuration
#
#     @classmethod
#     def load_configuration(cls, config, section):
#         """
#         Create a new configuration, based on the contents of a section loaded from a config file.
#
#         :param config: A configparser.ConfigParser instance.
#         :param section: The name of the section that should be loaded.
#         :return: A new configuration.
#         """
#         configuration_type = cls.get_configuration_type()
#         assert issubclass(configuration_type, Configuration)
#         return configuration_type.load_instance(config, section)
#
#     @classmethod
#     def load_instance(cls, config, section):
#         """
#         Create a new pre-configured instance of this class, based on the contents of a section loaded from a config
#         file.
#
#         :param config: A configparser.ConfigParser instance.
#         :param section: The name of the section the object should be configured from.
#         :return: A new, configured instance.
#         """
#         instance = cls.load_configuration(config, section).new_instance()
#         verify_type(instance, cls)
#         return instance
#
#     def __init__(self, configuration=None):
#         self._configuration = None
#         if configuration is not None:
#             self.configure(configuration)
#
#     @property
#     def is_configured(self):
#         """Whether the configurable object is in a usable state."""
#         return self._configuration is not None
#
#     @property
#     def is_reconfigurable(self):
#         """Whether the configurable object can be reconfigured."""
#         return True  # By default, reconfiguration is always allowed.
#
#     def verify_configured(self):
#         """If the instance is not configured, raise an exception."""
#         if not self.is_configured:
#             raise ObjectNotConfiguredError("The object is not configured.")
#
#     def get_configuration(self):
#         """
#         Return a copy of the configuration for this configurable object. (A copy is returned to prevent changes to
#         the configuration without the configured object's awareness.)
#
#         :return: A copy of this object's configuration.
#         """
#         if self._configuration is None:
#             return None
#         else:
#             assert isinstance(self._configuration, Configuration)
#             return self._configuration.copy()
#
#     def configure(self, configuration):
#         """
#         Configure this instance.
#
#         :param configuration: A Configuration instance.
#         :return: None
#         """
#         verify_type(configuration, self.get_configuration_type())
#         verify_type(self, configuration.connection_type)
#         if configuration == self._configuration:
#             return  # Nothing to do.
#         if not self.is_reconfigurable:
#             raise ObjectNotReconfigurableError("The object is not reconfigurable.")
#         configuration.validate()
#         self._configuration = configuration


class Configurable(metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        raise NotImplementedError()
