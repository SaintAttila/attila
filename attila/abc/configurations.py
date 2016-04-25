"""
Interface definition for configurable objects.
"""


from abc import ABCMeta, abstractmethod


__author__ = 'Aaron Hosford'
__all__ = [
    "Configurable",
]


class Configurable(metaclass=ABCMeta):
    """
    The Configurable class is an abstract base class for configurable objects.
    """

    @classmethod
    @abstractmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        raise NotImplementedError()
