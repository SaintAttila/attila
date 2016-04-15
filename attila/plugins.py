"""
attila.plugins
==============

Infrastructure for dealing with plugins.
"""

import warnings
from collections.abc import Mapping

import pkg_resources

from .abc.configurations import Configurable
from .exceptions import PluginExistsError, PluginNotFoundError, InvalidPluginError, verify_type

__all__ = [
    'PluginGroup',
    'CONFIG_LOADERS',
    'CONFIGURED_OBJECTS',
    'load_plugins',
    'load_object',
    'PluginExistsError',
    'PluginNotFoundError',
    'InvalidPluginError',
]


class PluginGroup(Mapping):
    """
    A PluginGroup is a collection of plugins registered under the same entry point group name. It supports both install-
    time and run-time registration of plugins, case-insensitive lookup by name, and plugin type-checking.
    """

    def __init__(self, name, value_type=None):
        verify_type(name, str, non_empty=True)
        if value_type is not None:
            verify_type(value_type, type)

        self._name = name
        self._value_type = value_type
        self._original_names = {}
        self._registry = {}

    def load(self, warn=True):
        """
        Load any pre-registered plugins.

        :param warn: Whether to warn if a registered plugin could not be loaded.
        :return: None
        """
        for entry_point in pkg_resources.iter_entry_points(group=self._name):
            try:
                self.register(entry_point.name, entry_point.load())
            except Exception as exc:
                if warn:
                    warnings.warn(str(exc))

    def register(self, name, value):
        """
        Register a new plugin.

        :param name: The name of the plugin.
        :param value: The plugin.
        :return: None
        """
        verify_type(name, str, non_empty=True)
        if name.lower() in self._registry and self._registry[name.lower()] != value:
            raise PluginExistsError("Another plugin by this name has already been registered: %s" % name)
        if self._value_type is not None and not isinstance(value, self._value_type):
            raise InvalidPluginError("Plugin %s is not a/an %s." % (name, self._value_type.__name__))
        self._original_names[name.lower()] = name
        self._registry[name.lower()] = value

    def __getitem__(self, name):
        if not isinstance(name, str):
            return NotImplemented
        if name.lower() not in self._registry:
            raise PluginNotFoundError(name)
        return self._registry[name.lower()]

    def __setitem__(self, name, value):
        if not isinstance(name, str):
            return NotImplemented
        self.register(name, value)

    def __iter__(self):
        return self._original_names.values()

    def __contains__(self, name):
        if not isinstance(name, str):
            return NotImplemented
        return name.lower() in self._registry

    def __len__(self):
        return len(self._registry)

    def get(self, name, default=None):
        """
        Get the plugin by name.

        :param name: The name of the plugin.
        :param default: The default value if the plugin does not exist.
        :return: The plugin, or the default.
        """
        verify_type(name, str, non_empty=True)
        return self._registry.get(name.lower(), default)


CONFIG_LOADERS = PluginGroup('attila.config_loader', value_type=Configurable)
URL_SCHEMES = PluginGroup('attila.url_scheme', value_type=Configurable)


def load_plugins(warn=True):
    """
    =============================================================================
    Load Attila Plugins
    =============================================================================

    Another package can register a plugin for use by attila by setting the entry_points parameter in the other package's
    setup.py script. See http://stackoverflow.com/a/9615473/4683578 and/or
    https://pythonhosted.org/setuptools/setuptools.use_html#dynamic-discovery-of-services-and-plugins for an explanation
    of how plugins work in Python.

    There are two distinct types of plugins that attila itself recognizes:
      * Configurable Types: These are loaded from the plugin group 'attila.configurable_type', and must be *subclasses*
        of the attila.abc.configurations.Configurable class, having a load_instance() class method which accepts a
        configparser.ConfigParser and a section name as its arguments.
      * Configured Objects: These are loaded from the plugin group 'attila.configured_object', and must be *instances*
        of the attila.abc.configurations.Configurable class.

    Each of these plugins is registered using the entry point name specified in the registering package's setup.py. The
    registered plugins can then be accessed via the attila.plugins.iter_*() and attila.plugins.get_*() methods.

    The Configurable Types are all loaded before any Configured Objects are loaded, allowing the Configurable Objects to
    be loaded, via the load_object() function, from a config section with a Type parameter that refers to a Configurable
    Type.
    """
    CONFIG_LOADERS.load(warn)
    # CONFIGURED_OBJECTS.load(warn)
    URL_SCHEMES.load(warn)


# def load_object(config, section, parameter=None, default=NotImplemented):
#     """
#     Load a configurable object from a config section or parameter.
#
#     :param config: A configparser.ConfigParser instance.
#     :param section: The section name.
#     :param parameter: The parameter name, if any.
#     :param default: A value to return if the required config section or parameter does not exist.
#     :return: The loaded object, or the default value.
#     """
#
#     verify_type(config, configparser.ConfigParser)
#     verify_type(section, str, non_empty=True)
#     if parameter is not None:
#         verify_type(parameter, str, non_empty=True)
#
#     if section not in config:
#         # We use NotImplemented as a sentinel so None can be a legal default value.
#         if default is NotImplemented:
#             raise ConfigSectionNotFoundError(section)
#         return default
#
#     if parameter is None:
#         # We are treating the entire section as a dynamically-typed object to be loaded.
#         config_section = config[section]
#         object_type_name = config_section['Type']
#         object_type = CONFIG_LOADERS[object_type_name]
#         return object_type.load_instance(config, section)
#
#     if parameter not in config[section]:
#         # We use NotImplemented as a sentinel so None can be a legal default value.
#         if default is NotImplemented:
#             raise ConfigParameterNotFoundError(section, parameter)
#         return default
#
#     raw_value = config[section][parameter]
#
#     if not raw_value.startswith('#'):
#         # If it isn't escaped, it's just a literal string value.
#         return raw_value
#
#     key = raw_value[1:]
#
#     if key.startswith('#'):
#         # It's just an escaped # character at the start of the value.
#         return key
#     elif key in CONFIGURED_OBJECTS and key not in config:
#         # It's the name of a configured object.
#         return CONFIGURED_OBJECTS[key]
#     else:
#         # It's the name of a section which should be loaded as an object.
#         return load_object(config, key, default=default)
