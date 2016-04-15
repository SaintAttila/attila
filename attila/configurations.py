"""
attila.configurations
=====================

Supports the automatic loading and configuration of compound objects directly from a configuration file.
"""

import configparser
import keyword

from . import plugins

from .abc.configurations import (Configurable, ConfigurationError, InvalidConfigurationError,
                                 ConfigSectionNotFoundError, ConfigParameterNotFoundError,
                                 ObjectNotConfiguredError, ObjectNotReconfigurableError,
                                 NoConfigurableInstanceTypeError)
from .exceptions import verify_type


__author__ = 'Aaron Hosford'

__all__ = [
    "ConfigLoader",
    "Configurable",
    "ConfigurationError",
    "InvalidConfigurationError",
    "ConfigSectionNotFoundError",
    "ConfigParameterNotFoundError",
    "ObjectNotConfiguredError",
    "ObjectNotReconfigurableError",
    "NoConfigurableInstanceTypeError",
]


# TODO: Add load_global_value() and load_global_function() as entry points in the attila.config_loaders group.
def load_global_value(name):
    """
    Safely convert a globally defined Python dotted name to the Python value it represents.

    :param name: The dotted name.
    :return: The Python value referenced by that name.
    """
    verify_type(name, str, non_empty=True)

    assert all(char.isalnum() or char in ('.', '_') for char in name)
    assert not any(keyword.iskeyword(piece) for piece in name.split('.'))

    # noinspection PyTypeChecker
    global_symbols = dict(globals())
    local_symbols = {}

    # We may need to import some modules to access the function.
    pieces = name.split('.')
    for index in range(1, len(pieces)):
        name = '.'.join(pieces[:index])
        try:
            local_symbols[name] = __import__(name, global_symbols, local_symbols)
        except ImportError:
            break

    return eval(name, global_symbols, local_symbols)


def load_global_function(name):
    """
    Safely convert a globally defined Python dotted name to the Python function it represents.

    :param name: The dotted name.
    :return: The Python function referenced by that name.
    """
    function = load_global_value(name)
    assert callable(function)
    return function


class ConfigLoader:
    """
    A ConfigLoader provides the ability to load compound objects from a configuration file.
    """

    def __init__(self, config, loaders=None):
        assert isinstance(config, configparser.ConfigParser)
        self._config = config
        self._loaders = plugins.CONFIG_LOADERS if loaders is None else loaders
        self._loaded_instances = {}

    @property
    def loaders(self):
        """A mapping (dictionary-like object) which maps from loader names to arbitrary functions or
        subclasses of Configurable which can be used to load options or sections from a config file."""
        return self._loaders

    def load_value(self, value, loader=None):
        """
        Load an arbitrary string value as an object. Behavior is identical to that of the load_option()
        method, including the ability to redirect to a section via a hashtag, except that the value is
        not indirectly accessed via a section and option.

        :param value: The string value to load.
        :param loader: The (optional) loader used to load the string value (or the section it points to).
            The loader can be a function, a subclass of Configurable, or the name of a registered loader.
        :return: The loaded object.
        """
        if value.startswith('#'):
            value = value[1:]
            if not value.startswith('#'):
                self.load_section(value, loader)

        if isinstance(loader, str):
            loader = self._loaders[loader]

        if isinstance(loader, type) and issubclass(loader, Configurable):
            return loader.load_config_option(self, value)
        else:
            return loader(value)

    def load_option(self, section, option, loader=None, default=NotImplemented):
        """
        Load an option (AKA parameter) from a specific section as an object. If the option value starts
        with a hash (#), it is treated as a reference to a config section whose value should be loaded
        and returned. If the option value starts with a double hash (##), the first hash is treated as
        an escape character and the remainder of the value is loaded instead of being treated as a
        hashtag. If a loader is provided, it will always be used. If no loader is provided and the
        value of the option is a hashtag, default section-loading semantics will be used. Otherwise,
        the value of the option will be returned as an ordinary string (str). Note that if the same
        option is loaded multiple times with the same loader, the object returned by the first call
        will be cached and returned again for later calls.

        :param section: The name of the section where the option appears.
        :param option: The name of the option to load.
        :param loader: The (optional) loader used to load the option (or the section it points to). The
            loader can be a function, a subclass of Configurable, or the name of a registered loader.
        :param default: The default value to use if the section or option does not exist. If no default
            value is specified, or the default is set to NotImplemented, an exception will be raised if
            the section or option does not exist. (Using NotImplemented for this instead of None enables
            the use of None as a default value.)
        :return: The loaded object, or the default value.
        """
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True)

        if not self._config.has_option(section, option) and default is not NotImplemented:
            return default

        content = self._config[section][option]

        if content.startswith('#'):
            content = content[1:]
            if not content.startswith('#'):
                return self.load_section(content, loader)

        if loader is None:
            loader = str
        elif isinstance(loader, str):
            loader = self._loaders[loader]

        cache_key = (section, option, loader)

        if cache_key in self._loaded_instances:
            return self._loaded_instances[cache_key]

        if isinstance(loader, type) and issubclass(loader, Configurable):
            result = loader.load_config_option(self, content)
        else:
            result = loader(content)

        self._loaded_instances[cache_key] = result

        return result

    def load_section(self, section, loader=None, default=NotImplemented):
        """
        Load a section as a single object. If a loader is provided, it will always be used. If no
        loader is provided, but a Type option appears in the section, the value of the Type option
        is used as the loader. If no loader is indicated by either of these mechanisms, the section
        is loaded as an ordinary dictionary (dict). Note that if the same section is loaded multiple
        times with the same loader, the object returned by the first call will be cached and returned
        again for later calls.

        :param section: The name of the section to load.
        :param loader: The (optional) loader used to load the section. The loader can be a function, a
            subclass of Configurable, or the name of a registered loader.
        :param default: The default value to use if the section does not exist. If no default value is
            specified, or the default is set to NotImplemented, an exception will be raised if the
            section does not exist. (Using NotImplemented for this instead of None enables the use of
            None as a default value.)
        :return: The loaded object.
        """
        verify_type(section, str, non_empty=True)

        if not self._config.has_section(section) and default is not NotImplemented:
            return default

        content = self._config[section]

        if loader is None:
            if 'Type' in content:
                loader = self.load_value(content['Type'])
            else:
                loader = dict
        if isinstance(loader, str):
            if loader in self._loaders:
                loader = self._loaders[loader]
            else:
                # TODO: We should probably offer a flag to turn this mechanism off; there will
                #       likely be cases where the user setting up the configuration should not
                #       be offered an arbitrary window into the code like this.
                loader = load_global_function(loader)

        cache_key = (section, None, loader)

        if cache_key in self._loaded_instances:
            return self._loaded_instances[cache_key]

        if isinstance(loader, type) and issubclass(loader, Configurable):
            result = loader.load_config_section(self, section)
        else:
            result = loader(content)

        self._loaded_instances[cache_key] = result

        return result

    def load(self, section, option=None, loader=None, default=NotImplemented):
        """
        Load a section or option as a single object. If an option is provided, behavior is
        identical to that of the load_option() method. If no option is provided, behavior is
        identical to that of the load_section() method. Note that if the same section or option
        is loaded multiple times with the same loader, the object returned by the first call
        will be cached and returned again for later calls.

        :param section: The section to load, or to load from.
        :param option: The (optional) option to load.
        :param loader: The (optional) loader used to load the section or option. The loader can be
            a function, a subclass of Configurable, or the name of a registered loader.
        :param default: The default value to use if the section or option does not exist. If no
            default value is specified, or the default is set to NotImplemented, an exception will
            be raised if the section or option does not exist. (Using NotImplemented for this
            instead of None enables the use of None as a default value.)
        :return: The loaded object.
        """
        if option is None:
            return self.load_section(section, loader, default)
        else:
            return self.load_option(section, option, loader, default)
