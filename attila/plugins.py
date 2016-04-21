"""
attila.plugins
==============

Infrastructure for dealing with plugins.
"""


import pkg_resources
import warnings

from collections.abc import Mapping


from .exceptions import PluginExistsError, PluginNotFoundError, InvalidPluginError, verify_type


__all__ = [
    'PluginGroup',
    'CONFIG_LOADERS',
    'URL_SCHEMES',
    'load_plugins',
]


class PluginGroup(Mapping):
    """
    A PluginGroup is a collection of plugins registered under the same entry point group name. It
    supports both install-time and run-time registration of plugins, case-insensitive lookup by
    name, and plugin type-checking.
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
            raise PluginExistsError("Another plugin by this name has already been registered: %s" %
                                    name)
        if self._value_type is not None and not isinstance(value, self._value_type):
            raise InvalidPluginError("Plugin %s is not a/an %s." %
                                     (name, self._value_type.__name__))
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

    def plugin(self, name=NotImplemented, value=NotImplemented):
        """
        A decorator for in-line registration of plugins.

        Registering a plugin function under its own name to group PLUGIN_GROUP:
            @PLUGIN_GROUP.plugin
            def aptly_named_plugin_function(arg1, arg2):
                ...

        Registering a plugin function to a different name to group PLUGIN_GROUP:
            @PLUGIN_GROUP.plugin('BetterPluginName')
            def less_aptly_named_plugin_function(arg1, arg2):
                ...

        :param value: The value to be registered as a plugin.
        :param name: The name to register the plugin under.
        :return: The value, unchanged, after registration, or a parameter-free plugin decorator.
        """

        assert name is not NotImplemented or value is not NotImplemented

        if name is NotImplemented:
            name = value.__name__

        verify_type(name, str, non_empty=True)

        if value is NotImplemented:
            def registrar(obj):
                """
                A parameter-free decorator for in-line registration of plugins.

                :param obj: The value to be registered as a plugin.
                :return: The value, unchanged, after registration.
                """
                self.register(name, obj)
                return obj

            return registrar

        self.register(name, value)

        return value


CONFIG_LOADERS = PluginGroup('attila.config_loader')
URL_SCHEMES = PluginGroup('attila.url_scheme')


def load_plugins(warn=True):
    """
    =============================================================================
    Load Attila Plugins
    =============================================================================

    Another package can register a plugin for use by attila by setting the entry_points parameter in
    the other package's setup.py script. See http://stackoverflow.com/a/9615473/4683578 and/or
    https://pythonhosted.org/setuptools/setuptools.use_html#dynamic-discovery-of-services-and-plugins
    for an explanation of how plugins work in Python.

    There are two distinct types of plugins that attila itself recognizes:
      * Config Loaders: These are loaded from the plugin group 'attila.config_loaders', and must be
        either subclasses of the attila.abc.configurations.Configurable class,
        class method which accepts a configparser.ConfigParser and a section name as its arguments.
      * Configured Objects: These are loaded from the plugin group 'attila.configured_object', and
        must be *instances* of the attila.abc.configurations.Configurable class.

    Each of these plugins is registered using the entry point name specified in the registering
    package's setup.py. The registered plugins can then be accessed via the attila.plugins.iter_*()
    and attila.plugins.get_*() methods.

    The Configurable Types are all loaded before any Configured Objects are loaded, allowing the
    Configurable Objects to be loaded, via the load_object() function, from a config section with a
    Type parameter that refers to a Configurable Type.
    """
    CONFIG_LOADERS.load(warn)
    URL_SCHEMES.load(warn)


def config_loader(name=NotImplemented, value=NotImplemented):
    """
    A decorator for in-line registration of config loaders.

    Registering a config loader function under its own name:
        @config_loader
        def aptly_named_config_loader(string):
            ...

    Registering a config loader function under a different name:
        @config_loader('BetterConfigLoaderName')
        def less_aptly_named_config_loader(string):
            ...

    Registering a config loader class under its own name:
        @config_loader
        class AptlyNamedConfigLoader(attila.abc.configurations.Configurable):
            ...

    Registering a config loader class under a different name:
        @config_loader('BetterConfigLoaderName')
        class LessAptlyNamedConfigLoader(attila.abc.configurations.Configurable):
            ...

    :param name: The name to register the plugin under.
    :param value: The value to register as a plugin.
    :return: The value, unchanged, after registration, or a parameter-free plugin decorator.
    """

    return CONFIG_LOADERS.plugin(name, value)


def url_scheme(name=NotImplemented, value=NotImplemented):
    """
    A decorator for in-line registration of URL schemes.

    Registering a URL scheme function under its own name:
        @config_loader
        def aptly_named_url_scheme(string):
            ...

    Registering a URL scheme function under a different name:
        @config_loader('BetterConfigLoaderName')
        def less_aptly_named_url_scheme(string):
            ...

    :param name: The name to register the plugin under.
    :param value: The value to register as a plugin.
    :return: The value, unchanged, after registration, or a parameter-free plugin decorator.
    """

    return URL_SCHEMES.plugin(name, value)
