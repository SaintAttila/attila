"""
attila.configurations
=====================

Supports the automatic loading and configuration of compound objects directly from a configuration file.
"""

import configparser
import keyword
import os

from . import plugins

from .abc.configurations import (Configurable, ConfigurationError, InvalidConfigurationError,
                                 ConfigSectionNotFoundError, ConfigParameterNotFoundError,
                                 ObjectNotConfiguredError, ObjectNotReconfigurableError,
                                 NoConfigurableInstanceTypeError)
from .abc.files import Path
from .exceptions import verify_type


__author__ = 'Aaron Hosford'

__all__ = [
    "load_global_value",
    "load_global_function",
    "get_default_config_search_dirs",
    "iter_config_search_paths",
    "load_config",
    "ConfigLoader",
    "get_attila_config_loader",
    "get_automation_config_loader",
    "Configurable",
    "ConfigurationError",
    "InvalidConfigurationError",
    "ConfigSectionNotFoundError",
    "ConfigParameterNotFoundError",
    "ObjectNotConfiguredError",
    "ObjectNotReconfigurableError",
    "NoConfigurableInstanceTypeError",
]


_CONFIG_EXTENSIONS = (
    '.ini',
    '.cfg',
    '.conf',
    '',
)

_ATTILA_CONFIG_LOADER = None
_AUTOMATION_CONFIG_LOADER = None


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


def get_default_config_search_dirs(file_name_base=None):
    """
    Return a list containing the default configuration file search directories for a given config file name
    base. No checking is performed, so the directories returned may not exist.

    :param file_name_base: The name of the configuration file, minus the extension.
    :return: A list of directories in where the config file may be located, in order of descending
        precedence.
    """
    if file_name_base is None or file_name_base.lower() == 'attila':
        config_location = None
    else:
        # Careful with this recursion... We don't want an infinite loop.
        attila_config_loader = get_attila_config_loader()
        option_name = file_name_base.title() + ' Config'
        config_location = attila_config_loader.load_option('DEFAULT', option_name, str, default=None)
    if file_name_base is None:
        environ_location = None
    else:
        environ_location = os.environ.get(file_name_base.upper() + '_CONFIG')
    base_paths = [
        '.',
        config_location,
        environ_location,
        os.environ.get('ATTILA_CONFIG'),
        '~',
        '~/.automation',
        '~/.config/attila',
        '/etc/attila',
        os.path.dirname(__file__),
    ]
    return [base_path for base_path in base_paths if base_path is not None]


def iter_config_search_paths(file_name_base, dirs=None, extensions=None):
    """
    Iterate over the search paths for a configuration file. Only paths that actually exist are included.

    :param file_name_base: The name of the config file, minus the extension.
    :param dirs: The directories in which to search.
    :param extensions: The file name extensions to check for.
    :return: An iterator over the config files in order of descending precedence.
    """
    if dirs is None:
        dirs = get_default_config_search_dirs(file_name_base)
    if extensions is None:
        extensions = _CONFIG_EXTENSIONS
    covered = set()
    for base_path in dirs:
        base_path = os.path.expanduser(base_path)
        base_path = os.path.expandvars(base_path)
        base_path = os.path.abspath(base_path)
        base_path = os.path.normcase(base_path)
        base_path = os.path.normpath(base_path)
        if not os.path.isdir(base_path):
            continue
        for extension in extensions:
            full_path = os.path.join(base_path, file_name_base + extension)
            if full_path not in covered:
                covered.add(full_path)
                if os.path.isfile(full_path):
                    yield full_path


def load_config(file_name_base, dirs=None, extensions=None, error=False):
    """
    Load one or more configuration files in order of precedence.

    :param file_name_base: The name of the config file(s), minus the extension.
    :param dirs: The directories in which to search.
    :param extensions: The file name extensions to check for.
    :param error: Whether to raise exceptions when the parser cannot read a config file.
    :return: A configparser.ConfigParser instance containing the loaded parameters.
    """
    config = configparser.ConfigParser()
    for path in reversed(iter_config_search_paths(file_name_base, dirs, extensions)):
        # noinspection PyBroadException
        try:
            config.read(path)
        except Exception:
            if error:
                raise
    return config


class ConfigLoader:
    """
    A ConfigLoader provides the ability to load compound objects from a configuration file.
    """

    def __init__(self, config, loaders=None, fallbacks=None):
        if isinstance(config, str):
            if os.path.isfile(config):
                path = config
                config = configparser.ConfigParser()
                config.read(path)
            else:
                config = load_config(file_name_base=config)
        elif isinstance(config, Path):
            path = config
            config = configparser.ConfigParser()
            with path.open() as file:
                config.read_file(file)
        verify_type(config, configparser.ConfigParser)

        fallbacks = tuple(fallbacks or ())
        for fallback in fallbacks:
            verify_type(fallback, ConfigLoader)

        self._config = config
        self._loaders = plugins.CONFIG_LOADERS if loaders is None else loaders
        self._loaded_instances = {}
        self._fallbacks = fallbacks

    @property
    def loaders(self):
        """A mapping (dictionary-like object) which maps from loader names to arbitrary functions or
        subclasses of Configurable which can be used to load options or sections from a config file."""
        return self._loaders

    @property
    def fallbacks(self):
        """The other ConfigLoaders that are used for default values when none is provided."""
        return self._fallbacks

    def has_option(self, section, option):
        """
        Determine whether the given option exists.

        :param section: The name of the section where the option must appear.
        :param option: The name of the option.
        :return: Whether or not the option exists.
        """
        if self._config.has_option(section, option):
            return True
        return any(fallback.has_option(section, option) for fallback in self._fallbacks)

    def has_section(self, section):
        """
        Determine whether the given section exists.

        :param section: The name of the section.
        :return: Whether or not the section exists.
        """
        if self._config.has_section(section):
            return True
        return any(fallback.has_section(section) for fallback in self._fallbacks)

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

        if not self._config.has_option(section, option):
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigLoader)
                if fallback.has_option(section, option):
                    return fallback.load_option(section, option, loader)
            if default is not NotImplemented:
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

        if not self._config.has_section(section):
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigLoader)
                if fallback.has_section(section):
                    return fallback.load_section(section, loader)
            if default is not NotImplemented:
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


def get_attila_config_loader(error=False, refresh=False):
    """
    Get the configuration loader for the attila package. This is specifically configuring the
    behavior of attila itself, not for controlling the automations implemented on top of it. If you are
    looking for the global configuration settings shared among all automations, use
    get_automation_config_loader() instead.

    :param error: Whether to raise exceptions when the parser cannot read a config file.
    :param refresh: Whether to reload the configuration information from disk.
    :return: A ConfigLoader instance which can be used to load the attila-specific config settings.
    """
    global _ATTILA_CONFIG_LOADER
    if refresh or _ATTILA_CONFIG_LOADER is None:
        config = load_config('attila', error=error)
        _ATTILA_CONFIG_LOADER = ConfigLoader(config)
    assert isinstance(_ATTILA_CONFIG_LOADER, ConfigLoader)
    return _ATTILA_CONFIG_LOADER


def get_automation_config_loader(error=False, refresh=False):
    """
    Get the configuration loader for settings shared among all automations. This is distinct from the
    attila config loader, which configures the behavior of attila itself.

    :param error: Whether to raise exceptions when the parser cannot read a config file.
    :param refresh: Whether to reload the configuration information from disk.
    :return: A ConfigLoader instance which can be used to load the globally shared automation config
        settings.
    """
    global _AUTOMATION_CONFIG_LOADER
    if refresh or _AUTOMATION_CONFIG_LOADER is None:
        config = load_config('automation', error=error)
        _AUTOMATION_CONFIG_LOADER = ConfigLoader(config)
    assert isinstance(_AUTOMATION_CONFIG_LOADER, ConfigLoader)
    return _AUTOMATION_CONFIG_LOADER
