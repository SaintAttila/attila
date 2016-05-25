"""
Supports the automatic loading and configuration of compound objects directly from a configuration
file.
"""


# TODO: Create functions to auto-generate the attila and automation config files.


import configparser
import keyword
import os
import threading


# This has to be imported like this to avoid an import cycle.
import attila.abc.files

from .exceptions import verify_type, verify_callable
from .plugins import URL_SCHEMES, CONFIG_LOADERS, config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    "load_global_value",
    "load_global_function",
    "get_default_config_search_dirs",
    "iter_config_search_paths",
    "load_config",
    "ConfigManager",
    "get_attila_config_manager",
    "get_automation_config_manager",
]


# These are underscored because they should not be accessed directly.
_attila_config_manager = None
_automation_config_manager = None
_GLOBALS_LOCK = threading.RLock()


CONFIG_EXTENSIONS = (
    '.ini',
    '.cfg',
    '.conf',
    # '',  # TODO: Do we want this or not?
)


INTERPOLATION_ESCAPE = '$'
INTERPOLATION_OPEN = '{'
INTERPOLATION_CLOSE = '}'
SECTION_OPTION_SEPARATOR = ':'
OBJECT_ESCAPE = '#'


@config_loader
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


@config_loader
def load_global_function(name):
    """
    Safely convert a globally defined Python dotted name to the Python function it represents.

    :param name: The dotted name.
    :return: The Python function referenced by that name.
    """
    function = load_global_value(name)
    verify_callable(function)
    return function


def get_default_config_search_dirs(file_name_base=None):
    """
    Return a list containing the default configuration file search directories for a given config
    file name base. No checking is performed, so the directories returned may not exist.

    :param file_name_base: The name of the configuration file, minus the extension.
    :return: A list of directories in where the config file may be located, in order of descending
        precedence.
    """
    if file_name_base is None or file_name_base.lower() == 'attila':
        config_location = None
    else:
        # Careful with this recursion... We don't want an infinite loop.
        attila_config_loader = get_attila_config_manager()
        option_name = file_name_base.title() + ' Config'
        config_location = attila_config_loader.load_option('DEFAULT', option_name, str,
                                                           default=None)
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
    base_paths = [base_path for base_path in base_paths if base_path is not None]
    if file_name_base is not None:
        base_paths = \
            [os.path.join(base_path, file_name_base) for base_path in base_paths] + base_paths
    return base_paths


def iter_config_search_paths(file_name_base, dirs=None, extensions=None):
    """
    Iterate over the search source_paths for a configuration file. Only source_paths that actually exist are
    included.

    :param file_name_base: The name of the config file, minus the extension.
    :param dirs: The directories in which to search.
    :param extensions: The file name extensions to check for.
    :return: An iterator over the config files in order of descending precedence.
    """
    if dirs is None:
        dirs = get_default_config_search_dirs(file_name_base)
    if extensions is None:
        extensions = CONFIG_EXTENSIONS
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
    for path in reversed(list(iter_config_search_paths(file_name_base, dirs, extensions))):
        # noinspection PyBroadException
        try:
            config.read(path)
        except Exception:
            if error:
                raise
    return config


class ConfigManager:
    """
    A ConfigManager manages the loading of compound objects directly from a configuration file.
    """

    def __init__(self, config, loaders=None, url_schemes=None, fallbacks=None):
        if isinstance(config, str):
            if os.path.isfile(config):
                path = config
                config = configparser.ConfigParser()
                config.read(path)
            else:
                config = load_config(file_name_base=config)
        elif isinstance(config, attila.abc.files.Path):
            path = config
            config = configparser.ConfigParser()
            with path.open() as file:
                config.read_file(file)
        verify_type(config, configparser.ConfigParser)

        fallbacks = tuple(fallbacks or ())
        for fallback in fallbacks:
            verify_type(fallback, ConfigManager)

        self._config = config
        self._loaders = CONFIG_LOADERS if loaders is None else loaders
        self._url_schemes = URL_SCHEMES if url_schemes is None else url_schemes
        self._loaded_instances = {}
        self._fallbacks = fallbacks

        self._loader_lock = threading.RLock()  # Lock for modifying/accessing loaders map
        self._url_scheme_lock = threading.RLock()  # Lock for modifying/accessing url scheme map
        self._config_lock = threading.RLock()  # Lock for modifying/accessing config object
        self._instance_lock = threading.RLock()  # Lock for modifying/accessing loaded instances map

    # TODO: Commented this out because it isn't thread-safe. If a simple workaround can be found,
    #       use it.
    # @property
    # def loaders(self):
    #     """
    #     A mapping (dictionary-like object) which maps from loader names to arbitrary functions or
    #     subclasses of Configurable which can be used to load options or sections from a config
    # file.
    #     """
    #     return self._loaders

    @property
    def fallbacks(self):
        """The other ConfigLoaders that are used for default values when none is provided."""
        return self._fallbacks

    def set_loader(self, name, loader):
        """
        Add a new config loader.

        :param name: The name of the new loader.
        :param loader: The loader.
        """
        verify_type(name, str, non_empty=True)
        with self._loader_lock:
            self._loaders[name] = loader

    def has_loader(self, name):
        """
        Return whether the given loader is available.

        :param name: The name of the loader.
        :return: Whether the loader is available.
        """
        verify_type(name, str, non_empty=True)
        with self._loader_lock:
            if name in self._loaders:
                return True
            return any(fallback.has_loader(name) for fallback in self._fallbacks)

    def get_loaders(self):
        """
        Return the set of available loader names.
        """
        with self._loader_lock:
            loaders = set(self._loaders)
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                loaders.update(fallback.get_loaders())
            return loaders

    def get_loader(self, name, default=NotImplemented):
        """
        Lookup a loader by name.

        :param name: The name of the loader.
        :param default: The default value returned if no such loader exists.
        :return: The loader, or the default if no such loader is available.
        """
        verify_type(name, str, non_empty=True)
        with self._loader_lock:
            if name in self._loaders:
                return self._loaders[name]
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                if fallback.has_loader(name):
                    return fallback.get_loader(name, default)
            if default is NotImplemented:
                raise KeyError(name)
            return default

    def set_url_scheme(self, name, scheme):
        """
        Add a new URL scheme.

        :param name: The name of the new scheme.
        :param scheme: The parser for the scheme.
        """
        verify_type(name, str, non_empty=True)
        with self._url_scheme_lock:
            self._url_schemes[name] = scheme

    def has_url_scheme(self, name):
        """
        Return whether the given URL scheme is available.

        :param name: The name of the URL scheme.
        :return: Whether the URL scheme is available.
        """
        verify_type(name, str, non_empty=True)
        with self._url_scheme_lock:
            if name in self._url_schemes:
                return True
            return any(fallback.has_url_scheme(name) for fallback in self._fallbacks)

    def get_url_schemes(self):
        """
        Return the set of available URL scheme names.
        """
        with self._url_scheme_lock:
            schemes = set(self._url_schemes)
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                schemes.update(fallback.get_url_schemes())
            return schemes

    def get_url_scheme(self, name, default=NotImplemented):
        """
        Lookup a URL scheme by name.

        :param name: The name of the URL scheme.
        :param default: The default value returned if no such URL scheme exists.
        :return: The URL scheme, or the default if no such scheme is available.
        """
        verify_type(name, str, non_empty=True)
        with self._url_scheme_lock:
            if name in self._url_schemes:
                return self._url_schemes[name]
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                if fallback.has_url_scheme(name):
                    return fallback.get_url_scheme(name, default)
            if default is NotImplemented:
                raise KeyError(name)
            return default

    def set_section(self, section, content):
        """
        Set the content of a section. IMPORTANT: This does not affect fallbacks.

        :param section: The name of the section.
        :param content: A dictionary or other mapping from options to values.
        """
        verify_type(section, str, non_empty=True)
        content = dict(content)
        for option, value in content.items():
            verify_type(option, str, non_empty=True)
            verify_type(value, str)

        with self._config_lock:
            # First, clear out the section.
            if self._config.has_section(section):
                self._config.remove_section(section)

            # Then add it back.
            self._config.add_section(section)

            # Then populate it.
            for option, value in content.items():
                self._config.set(section, option, value)

    def remove_section(self, section):
        """
        Remove a section. IMPORTANT: This does not affect fallbacks.

        :param section: The name of the section.
        """
        verify_type(section, str, non_empty=True)
        with self._config_lock:
            self._config.remove_section(section)

    def has_section(self, section):
        """
        Determine whether the given section exists.

        :param section: The name of the section.
        :return: Whether or not the section exists.
        """
        verify_type(section, str, non_empty=True)
        if section == 'DEFAULT':
            return True
        with self._config_lock:
            if self._config.has_section(section):
                return True
            return any(fallback.has_section(section) for fallback in self._fallbacks)

    def get_sections(self):
        """
        Return the set of available section names.
        """
        with self._config_lock:
            sections = set(self._config)
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                sections.update(fallback.get_sections())
            return sections

    def get_section(self, section, default=NotImplemented):
        """
        Return a dictionary with the contents of the section. Note that modifying the dictionary
        does NOT modify the underlying configuration.

        :param section: The name of the section.
        :param default: The default value if the section does not exist.
        :return: A dictionary containing the section's contents, or the default if no such section
            exists.
        """
        verify_type(section, str, non_empty=True)
        with self._config_lock:
            # I don't know why, but configparser.ConfigParser will fetch the DEFAULT section and
            # include it in the listed sections, and yet when you call has_section() it will return
            # False. We attempt to supply the correct behavior, always showing that the DEFAULT
            # section exists no matter which way it's checked.
            found = False or (section == 'DEFAULT')
            results = {}
            for fallback in reversed(self._fallbacks):
                assert isinstance(fallback, ConfigManager)
                try:
                    results.update(fallback.get_section(section))
                except KeyError:
                    pass
                else:
                    found = True
            if self._config.has_section(section):
                found = True
                results.update(self._config[section])
            if found:
                return results
            elif default is NotImplemented:
                raise KeyError(section)
            else:
                return default

    def set_option(self, section, option, value):
        """
        Set the value of an option. IMPORTANT: This does not affect fallbacks.

        :param section: The name of the section.
        :param option: The name of the option.
        :param value: The value of the option.
        """
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True)
        verify_type(value, str)
        with self._config_lock:
            if section != 'DEFAULT' and not self._config.has_section(section):
                self._config.add_section(section)
            self._config.set(section, option, value)

    def remove_option(self, section, option):
        """
        Remove an option from a section. IMPORTANT: This does not affect fallbacks.

        :param section: The name of the section.
        :param option: The name of the option.
        """
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True)
        with self._config:
            self._config.remove_option(section, option)

    def has_option(self, section, option):
        """
        Determine whether the given option exists.

        :param section: The name of the section where the option must appear.
        :param option: The name of the option.
        :return: Whether or not the option exists.
        """
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True)
        with self._config_lock:
            if self._config.has_option(section, option):
                return True
            return any(fallback.has_option(section, option) for fallback in self._fallbacks)

    def get_options(self, section):
        """
        Return the set of available option names in a section.

        :param section: The name of the section.
        :return: A set containing the option names.
        """
        verify_type(section, str, non_empty=True)
        with self._config_lock:
            options = set()
            if self._config.has_section(section):
                options.update(self._config[section])
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                options.update(fallback.get_options(section))
            return options

    def interpolate(self, value, default_section=None):
        """
        Apply string interpolation to the value.

        :param value: The value to be interpolated.
        :param default_section: The default section to load from if none is specified.
        :return: The string value resulting from interpolation.
        """
        verify_type(value, str)
        assert isinstance(value, str)
        verify_type(default_section, str, non_empty=True, allow_none=True)

        result = ''
        escaped = False
        opened = False
        content = ''
        for char in value:
            if opened:
                if char == INTERPOLATION_CLOSE:
                    escaped = False
                    opened = False
                    if content.count(SECTION_OPTION_SEPARATOR) == 1:
                        section, option = content.split(SECTION_OPTION_SEPARATOR)
                    else:
                        assert default_section is not None
                        section = default_section
                        option = content
                    result += self.get_option(section, option)
                    content = ''
                else:
                    content += char
            elif char == INTERPOLATION_ESCAPE:
                escaped = not escaped
            elif escaped:
                if char == INTERPOLATION_OPEN:
                    opened = True
                    assert not content
                elif char == INTERPOLATION_ESCAPE:
                    escaped = False
                    result += char
                else:
                    escaped = False
                    result += INTERPOLATION_ESCAPE + char
            else:
                result += char
        if content:
            # If we have a section that wasn't closed, treat the whole thing as a literal string.
            if escaped:
                result += INTERPOLATION_ESCAPE
            if opened:
                result += INTERPOLATION_OPEN
            result += content
        return result

    def get_option(self, section, option, default=NotImplemented, raw=False):
        """
        Return the raw string value of the option.

        :param section: The section name.
        :param option: The option name.
        :param default: The default value to return if no such option exists.
        :param raw: Whether string interpolation should be avoided.
        :return: The raw string value of the option, or the default if it doesn't exist.
        """
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True)
        with self._config_lock:
            if self._config.has_option(section, option):
                value = self._config[section][option]
                if raw:
                    return value
                else:
                    return self.interpolate(value, section)
            for fallback in self._fallbacks:
                assert isinstance(fallback, ConfigManager)
                if fallback.has_option(section, option):
                    value = fallback.get_option(section, option, default, raw=True)
                    if raw:
                        return value
                    else:
                        return self.interpolate(value, section)
            if default is NotImplemented:
                if self.has_section(section):
                    raise KeyError(option)
                else:
                    raise KeyError(section)
            return default

    def _load_object(self, value, loader=None):
        assert not value.startswith(OBJECT_ESCAPE)
        if SECTION_OPTION_SEPARATOR in value:
            section, option = value.split(SECTION_OPTION_SEPARATOR)
            return self.load_option(section, option, loader)
        else:
            return self.load_section(value, loader)

    def load_value(self, value, loader=None):
        """
        Load an arbitrary string value as an object. Behavior is identical to that of the
        load_option() method, including the ability to redirect to a section via interpolation,
        except that the value is not indirectly accessed via a section and option.

        :param value: The string value to load.
        :param loader: The (optional) loader used to load the string value (or the section it points
            to). The loader can be a function, a subclass of Configurable, or the name of a
            registered loader.
        :return: The loaded object.
        """
        verify_type(value, str)

        if value.startswith(OBJECT_ESCAPE):
            value = value[1:]
            if not value.startswith(OBJECT_ESCAPE):
                return self._load_object(value, loader)

        if isinstance(loader, str):
            loader = self.get_loader(loader)
        elif loader is None:
            loader = str

        if hasattr(loader, 'load_config_value'):
            return loader.load_config_value(self, value)
        else:
            return loader(value)

    def load_path(self, url, scheme=None):
        """
        Load a URL string as a Path instance.

        :param url: The url to load.
        :param scheme: The (optional) scheme to parse the url as.
        :return: The loaded path.
        """
        verify_type(url, str, non_empty=True)

        if callable(scheme):
            return scheme(url)

        verify_type(scheme, str, non_empty=True, allow_none=True)

        if '://' in url:
            explicit_scheme = url.split('://')[0]
            if scheme is None:
                scheme = explicit_scheme
            else:
                assert scheme.lower() == explicit_scheme.lower()
        elif scheme is None:
            scheme = 'file'

        scheme = self.get_url_scheme(scheme)
        if hasattr(scheme, 'load_url'):
            path = scheme.load_url(self, url)
        else:
            path = scheme(url)

        assert isinstance(path, attila.abc.files.Path)
        return path

    def load_option(self, section, option, loader=None, default=NotImplemented):
        """
        Load an option (AKA parameter) from a specific section as an object. If the option value
        starts with the config interpolation character ($), it is treated as a reference to a config
        section whose value should be loaded and returned. If the option value starts with a
        doubling of the config interpolation character ($$), the first one is treated as an escape
        character and the remainder of the value is loaded instead of being treated as an
        interpolation. If a loader is provided, it will always be used. If no loader is provided and
        the value of the option is an interpolation, default section-loading semantics will be used.
        Otherwise, the value of the option will be returned as an ordinary string (str). Note that
        if the same option is loaded multiple times with the same loader, the object returned by the
        first call will be cached and returned again for later calls.

        :param section: The name of the section where the option appears.
        :param option: The name of the option to load.
        :param loader: The (optional) loader used to load the option (or the section it points to).
            The loader can be a function, a subclass of Configurable, or the name of a registered
            loader.
        :param default: The default value to use if the section or option does not exist. If no
            default value is specified, or the default is set to NotImplemented, an exception will
            be raised if the section or option does not exist. (Using NotImplemented for this
            instead of None enables the use of None as a default value.)
        :return: The loaded object, or the default value.
        """
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True)

        try:
            content = self.get_option(section, option)
        except KeyError:
            if default is NotImplemented:
                raise
            else:
                return default

        if isinstance(loader, str):
            loader = self.get_loader(loader)

        if content.startswith(OBJECT_ESCAPE):
            content = content[1:]
            if not content.startswith(OBJECT_ESCAPE):
                return self._load_object(content, loader)

        if loader is None:
            loader = str

        cache_key = (section, option, loader)

        with self._instance_lock:
            if cache_key in self._loaded_instances:
                return self._loaded_instances[cache_key]

            if hasattr(loader, 'load_config_value'):
                result = loader.load_config_value(self, content)
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
        times with the same loader, the object returned by the first call will be cached and
        returned again for later calls.

        :param section: The name of the section to load.
        :param loader: The (optional) loader used to load the section. The loader can be a function,
            a subclass of Configurable, or the name of a registered loader.
        :param default: The default value to use if the section does not exist. If no default value
            is specified, or the default is set to NotImplemented, an exception will be raised if
            the section does not exist. (Using NotImplemented for this instead of None enables the
            use of None as a default value.)
        :return: The loaded object.
        """
        verify_type(section, str, non_empty=True)

        try:
            content = self.get_section(section)
        except KeyError:
            if default is NotImplemented:
                raise
            else:
                return default

        if loader is None:
            if 'type' in content:
                loader = self.load_value(content['type'])
            else:
                loader = dict

        if isinstance(loader, str):
            with self._loader_lock:
                if self.has_loader(loader):
                    loader = self.get_loader(loader)
                else:
                    # TODO: We should probably offer a flag to turn this mechanism off; there will
                    #       likely be cases where the user setting up the configuration should not
                    #       be offered an arbitrary window into the code like this.
                    loader = load_global_function(loader)

        cache_key = (section, None, loader)

        with self._instance_lock:
            if cache_key in self._loaded_instances:
                return self._loaded_instances[cache_key]

            if hasattr(loader, 'load_config_section'):
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
        verify_type(section, str, non_empty=True)
        verify_type(option, str, non_empty=True, allow_none=True)
        if option is None:
            return self.load_section(section, loader, default)
        else:
            return self.load_option(section, option, loader, default)


def get_attila_config_manager(error=False, refresh=False):
    """
    Get the configuration manager for the attila package. This is specifically configuring the
    behavior of attila itself, not for controlling the automations implemented on top of it. If you
    are looking for the global configuration settings shared among all automations, use
    get_automation_config_manager() instead.

    :param error: Whether to raise exceptions when the parser cannot read a config file.
    :param refresh: Whether to reload the configuration information from disk.
    :return: A ConfigManager instance which can be used to load the attila-specific config settings.
    """
    with _GLOBALS_LOCK:
        global _attila_config_manager
        if refresh or _attila_config_manager is None:
            config = load_config('attila', error=error)
            _attila_config_manager = ConfigManager(config)
        assert isinstance(_attila_config_manager, ConfigManager)
        return _attila_config_manager


def get_automation_config_manager(error=False, refresh=False):
    """
    Get the configuration manager for settings shared among all automations. This is distinct from
    the attila config manager, which configures the behavior of attila itself.

    :param error: Whether to raise exceptions when the parser cannot read a config file.
    :param refresh: Whether to reload the configuration information from disk.
    :return: A ConfigManager instance which can be used to load the globally shared automation
        config settings.
    """
    with _GLOBALS_LOCK:
        global _automation_config_manager
        if refresh or _automation_config_manager is None:
            config = load_config('automation', error=error)
            _automation_config_manager = \
                ConfigManager(config, fallbacks=[get_attila_config_manager(error, refresh)])
        assert isinstance(_automation_config_manager, ConfigManager)
        return _automation_config_manager
