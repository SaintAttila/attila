import pkg_resources
import warnings

from collections.abc import Mapping


__author__ = 'Aaron Hosford'


class PluginGroup(Mapping):

    def __init__(self, name, require_config_loader=False):
        assert name and isinstance(name, str)
        assert require_config_loader == bool(require_config_loader)

        self._name = name
        self._require_config_loader = bool(require_config_loader)
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
        assert name and isinstance(name, str)
        if name.lower() in self._registry and self._registry[name.lower()] is not value:
            raise KeyError(name)  # Another plugin by this name has already been registered.
        if self._require_config_loader:
            assert hasattr(value, 'load_from_config')
            assert callable(value.load_from_config)
        self._original_names[name.lower()] = name
        self._registry[name.lower()] = value

    def __getitem__(self, name):
        if not isinstance(name, str):
            return NotImplemented
        if name.lower() not in self._registry:
            raise KeyError(name)
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
        assert isinstance(name, str)
        return self._registry.get(name.lower(), default)


CHANNEL_TYPES = PluginGroup('attila.channel_type', require_config_loader=True)
CHANNELS = PluginGroup('attila.channel')
NOTIFIER_TYPES = PluginGroup('attila.notifier_type', require_config_loader=True)
NOTIFIERS = PluginGroup('attila.notifier')


def _load_plugins(warn=True):
    """
    =============================================================================
    Load Attila Plugins
    =============================================================================

    Another package can register a plugin for use by attila by setting the entry_points parameter in the other package's
    setup.py script. See http://stackoverflow.com/a/9615473/4683578 and/or
    https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins for an explanation of
    how plugins work in Python.

    There are currently four distinct types of plugins for attila:
      * Channel Types: These are loaded from the plugin group 'attila.channel_type', and must be *subclasses* of the
        attila.notifications.Channel class, having a load_from_config() class method which accepts a
        configparser.ConfigParser and a section name as its arguments.
      * Channels: These are loaded from the plugin group 'attila.channel', and must be *instances* of the
        attila.notifications.Channel class.
      * Notifier Types: These are loaded from the plugin group 'attila.notifier_type', and must be *subclasses* of the
        attila.notifications.Notifier class, having a load_from_config() class method which accepts a
        configparser.ConfigParser and a section name as its arguments.
      * Notifiers: These are loaded from the plugin group 'attila.notifier', and must be *instances* of the
        attila.notifications.Notifier class.

    Each of these plugins is registered using the entry point name specified in the registering package's setup.py. The
    registered plugins can then be accessed via the attila.plugins.iter_*() and attila.plugins.get_*() methods.
    """
    CHANNEL_TYPES.load(warn)
    CHANNELS.load(warn)
    NOTIFIER_TYPES.load(warn)
    NOTIFIERS.load(warn)
