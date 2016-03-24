"""
attila.env
==========

Environment and settings.
"""

import configparser
import datetime
import inspect
import os

import attila.plugins
from . import notifications


__all__ = [
    'get_default_config_search_dirs',
    'iter_search_paths',
    'load_config',
    'get_attila_config',
    'get_automation_config',
    'get_entry_point_name',
    'automation_environment',
]


_CONFIG_EXTENSIONS = (
    '.ini',
    '.cfg',
    '.conf',
    '',
)

_ATTILA_CONFIG = None
_AUTOMATION_CONFIG = None


def get_default_config_search_dirs(file_name_base=None):
    """
    Return a list containing the default configuration file search directories for a given config file name base. No
    checking is performed, so the directories returned may not exist.

    :param file_name_base: The name of the configuration file, minus the extension.
    :return: A list of directories in where the config file may be located, in order of descending precedence.
    """
    if file_name_base is None or file_name_base.lower() == 'attila':
        config_location = None
    else:
        # Careful with this recursion... We don't want an infinite loop.
        attila_config = get_attila_config()
        config_location = attila_config['DEFAULT'].get(file_name_base.title() + ' Config')
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


def iter_search_paths(file_name_base, dirs=None, extensions=None):
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
    for path in reversed(iter_search_paths(file_name_base, dirs, extensions)):
        # noinspection PyBroadException
        try:
            config.read(path)
        except Exception:
            if error:
                raise
    return config


def get_attila_config(error=False, refresh=False):
    """
    Load the configuration settings for the attila package. This is for specifically controlling the behavior of attila
    itself, not for controlling the automations implemented on top of it. If you are looking for the global
    configuration settings shared among all automations, use get_automation_config() instead.

    :param error: Whether to raise exceptions when the parser cannot read a config file.
    :param refresh: Whether to reload the configuration information from disk.
    :return: A configparser.ConfigParser instance containing the attila-specific config settings.
    """
    global _ATTILA_CONFIG
    if refresh or _ATTILA_CONFIG is None:
        _ATTILA_CONFIG = load_config('attila', error=error)
    assert isinstance(_ATTILA_CONFIG, configparser.ConfigParser)
    return _ATTILA_CONFIG


def get_automation_config(error=False, refresh=False):
    """
    Load the configuration settings shared among all automations. This is not
    :param error:
    :param refresh: Whether to reload the configuration information from disk.
    :return:
    """
    global _AUTOMATION_CONFIG
    if refresh or _AUTOMATION_CONFIG is None:
        _AUTOMATION_CONFIG = load_config('automation', error=error)
    assert isinstance(_AUTOMATION_CONFIG, configparser.ConfigParser)
    return _AUTOMATION_CONFIG


def get_entry_point_name(default=None):
    """
    Locate the module closest to where execution began and return its name. If no module could be identified (which can
    sometimes occur when running from some IDEs when a module is run without being saved first), returns default.

    :param default: The default return value if no module could be identified.
    :return: The name of the identified module, or the default value.
    """
    # My apologies in advance for what you are about to witness here...
    frame = inspect.currentframe()
    result = default
    while frame:
        f_code = getattr(frame, 'f_code', None)
        if f_code:
            co_filename = getattr(f_code, 'co_filename', None)
            if co_filename:
                result = inspect.getmodulename(co_filename) or result
            if getattr(f_code, 'co_name', None) == '<module>':
                break  # Anything after this point is just bootstrapping code and should be ignored.
        frame = getattr(frame, 'f_back', None)
    return result


class automation_environment:
    """
    Interface for automation processes to access environment and configuration settings.
    """

    @staticmethod
    def _fill_parameter(template, time_stamp, mapping):
        assert isinstance(template, str)
        assert isinstance(time_stamp, datetime.datetime)
        return time_stamp.strftime(template.format_map(mapping))

    def __init__(self, name=None, config=None, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        else:
            assert isinstance(start_time, datetime.datetime)

        if name is None:
            name = get_entry_point_name('UNKNOWN')
        elif not name:
            name = 'UNKNOWN'
        assert name
        assert isinstance(name, str)

        if config is None:
            config = load_config(name)
        assert isinstance(config, configparser.ConfigParser)

        automation_config = get_automation_config()

        env_section = automation_config.get('Environment', {})

        automation_root_dir = env_section.get('Root Path') or '~/.automation'

        default_workspace = env_section.get('Workspace Path') or os.path.join('{root}', 'workspace')
        default_log_dir = env_section.get('Logging Path') or os.path.join('{root}', 'logs')
        default_docs_dir = env_section.get('Documentation Path') or os.path.join('{root}', 'docs')
        default_data_dir = env_section.get('Data Path') or os.path.join('{root}', 'data')
        default_log_file_name = env_section.get('Log File Name') or '{name}_%Y%m%d%H%M%S.log'
        default_log_format = env_section.get('Log Format') or '%(asctime)s_pid:%(process)d ~*~ %(message)s'
        default_error_channel = env_section.get('Error Channel')

        mapping = {
            'name': name,
            'root': automation_root_dir
        }

        workspace = config['Environment'].get('Workspace Path') or os.path.join(default_workspace, '{name}')
        log_dir = config['Environment'].get('Logging Path') or os.path.join(default_log_dir, '{name}')
        data_dir = config['Environment'].get('Data Path') or os.path.join(default_data_dir, '{name}')
        docs_dir = config['Environment'].get('Documentation Path') or os.path.join(default_docs_dir, '{name}')
        log_file_name = config['Environment'].get('Log File Name') or default_log_file_name
        log_format = config['Environment'].get('Log Format') or default_log_format

        workspace = self._fill_parameter(workspace, start_time, mapping)
        log_dir = self._fill_parameter(log_dir, start_time, mapping)
        data_dir = self._fill_parameter(data_dir, start_time, mapping)
        docs_dir = self._fill_parameter(docs_dir, start_time, mapping)
        log_file_name = self._fill_parameter(log_file_name, start_time, mapping)

        log_file_path = os.path.join(log_dir, log_file_name)

        # TODO: Load and use default notifiers.
        # TODO: Integrate these notifiers into the environment, so notifications are automatically sent at the appropriate times.
        start_notifier = attila.plugins.load_notifier_from_config(config, 'Start Notifier')  # Script start
        success_notifier = attila.plugins.load_notifier_from_config(config, 'Success Notifier')  # Script success (not necessarily terminated)
        failure_notifier = attila.plugins.load_notifier_from_config(config, 'Failure Notifier')  # Script failure (not necessarily terminated or an error)
        error_notifier = attila.plugins.load_notifier_from_config(config, 'Error Notifier')  # Script error (not necessarily terminated or a failure)
        end_notifier = attila.plugins.load_notifier_from_config(config, 'End Notifier')  # Script termination (not necessarily a success)

        self._name = name
        self._config = config
        self._workspace = workspace
        self._log_dir = log_dir
        self._docs_dir = docs_dir
        self._data_dir = data_dir
        self._log_file_path = log_file_path
        self._log_format = log_format
        self._error_notifier = error_notifier

    @property
    def name(self):
        """
        The name of the automation.

        :return: A non-empty str instance.
        """
        return self._name

    @property
    def config(self):
        """
        The config settings for this automation.

        :return: A configparser.ConfigParser instance.
        """
        return self._config

    @property
    def workspace(self):
        """
        The directory the automation should use for performing file operations and storing persistent state.

        :return: A directory path, as a str instance.
        """
        return self._workspace

    @property
    def log_dir(self):
        """
        The directory the automation should use for log files.

        :return: A directory path, as a str instance.
        """
        return self._log_dir

    @property
    def log_file_path(self):
        """
        The path to the log file the automation should log to.

        :return: A file path, as a str instance.
        """
        return self._log_file_path

    @property
    def docs_dir(self):
        """
        The directory where permanent documentation for the automation should be stored.

        :return: A directory path, as a str instance.
        """
        return self._docs_dir

    @property
    def data_dir(self):
        """
        The directory where permanent read-only data used by the automation should be stored.

        :return: A directory path, as a str instance.
        """
        return self._data_dir

    @property
    def error_notifier(self):
        return self._error_notifier

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type or exc_val or exc_tb:
            self._error_notifier.send(exc_type, exc_val, exc_tb)
        return False  # Do not suppress exceptions.
