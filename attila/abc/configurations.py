"""
attila.abc.configurables
========================

Interface definition for configurable objects.
"""


from abc import ABCMeta, abstractmethod


__all__ = [
    "Configurable",
]


class Configurable(metaclass=ABCMeta):
    """
    The Configurable class is an abstract base class for configurable objects.
    """

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
