from abc import ABCMeta, abstractmethod
import configparser


__all__ = [
    "Configurable",
]


# TODO: Make the various configurable classes in this library inherit from this.
class Configurable(metaclass=ABCMeta):
    """
    The Configurable class is an abstract base class for configurable objects.
    """

    @classmethod
    def load_from_config(cls, config, section):
        """
        Create a new pre-configured instance of this class and return it.

        :param config: A configparser.ConfigParser instance.
        :param section: The name of the section the object should be configured from.
        :return: A new, configured instance.
        """
        instance = cls()
        instance.configure(config, section)
        return instance

    @abstractmethod
    def configure(self, config, section):
        """
        Configure this instance based on the contents of a section loaded from a config file.

        :param config: A configparser.ConfigParser instance.
        :param section: The name of the section the object should be configured from.
        :return: None
        """
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        raise NotImplementedError()

    @property
    @abstractmethod
    def is_configured(self):
        """Whether the configurable object is in a usable state."""
        raise NotImplementedError()
