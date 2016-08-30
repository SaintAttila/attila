"""
A standardized automation environment
"""

import datetime
import getpass
import inspect
import logging
import os
import socket
import threading
import traceback
import warnings
from functools import wraps

from .abc.files import Path
from .configurations import get_automation_config_manager, ConfigManager, iter_config_search_paths
from .exceptions import verify_type, verify_callable
from .logging import Logger
from .notifications.parameters import notification_parameters, SUCCESS_EVENT, FAILURE_EVENT, START_EVENT, END_EVENT, \
    EXCEPTION_EVENT
from .utility import last

__author__ = 'Aaron Hosford'
__all__ = [
    'get_entry_point_name',
    'task',
    'automation',
    'auto_context',
]


def _get_entry_point_stack_frame():
    # My apologies in advance for what you are about to witness here...
    frame = inspect.currentframe()
    result = None
    while frame:
        f_code = getattr(frame, 'f_code', None)
        if f_code:
            co_filename = getattr(f_code, 'co_filename', None)
            if co_filename:
                module_name = inspect.getmodulename(co_filename)
                if module_name == '__init__':
                    module_name = os.path.basename(os.path.dirname(co_filename))
                if module_name:
                    result = frame
            if getattr(f_code, 'co_name', None) == '<module>':
                break  # Anything after this point is just bootstrapping code and should be ignored.
        frame = getattr(frame, 'f_back', None)
    return result


def get_entry_point_name(default=None, use_context=True):
    """
    Locate the module closest to where execution began and return its name. If no module could be
    identified (which can sometimes occur when running from some IDEs when a module is run without
    being saved first), returns default.

    :param default: The default return value if no module could be identified.
    :param use_context: Whether to use the current automation context, if one is available.
    :return: The name of the identified module, or the default value.
    """

    if use_context:
        # First, check to see if we have an automation context; this will be the most reliable means
        # of determining the correct name, if it is available.
        current_context = auto_context.current()
        if current_context is not None:
            assert isinstance(current_context, auto_context)
            if current_context.name and current_context.name != 'UNKNOWN':
                return current_context.name

    frame = _get_entry_point_stack_frame()

    if frame is not None:
        co_filename = frame.f_code

        module_name = inspect.getmodulename(co_filename)
        if module_name == '__init__':
            module_name = os.path.basename(os.path.dirname(co_filename))
        if module_name:
            return module_name

    return default


def get_entry_point_version(default=None, use_context=True):
    """
    Locate the module closest to where execution began and return its version number. If no module
    could be identified (which can sometimes occur when running from some IDEs when a module is run
    without being saved first), returns default.

    :param default: The default return value if no module could be identified.
    :param use_context: Whether to use the current automation context, if one is available.
    :return: The version number string of the identified module, or the default value.
    """

    if use_context:
        # First, check to see if we have an automation context; this will be the most reliable means
        # of determining the correct name, if it is available.
        current_context = auto_context.current()
        if current_context is not None:
            assert isinstance(current_context, auto_context)
            if current_context.version is not None:
                return current_context.version

    frame = _get_entry_point_stack_frame()

    if frame is not None:
        globals_dict = frame.f_globals

        for attribute in ('__version__', 'version'):
            if attribute in globals_dict:
                return globals_dict[attribute]

    return default


class task:
    """
    Use with the 'with' statement to automatically track what task is being performed.

    Example Usage:
        with task("Doing stuff..."):
            print("Now I'm doing stuff.")

            with task("Doing more detailed stuff..."):
                print("This is getting complicated.")

    If and when an error occurs, the nested tasks that were failed will automatically generate
    notifications. Notifications are also generated automatically when the with block is entered
    and exited cleanly. The default notifiers can be set at the automation level:

        automation.current().task_start_notifier = start_notifier
        automation.current().task_success_notifier = success_notifier
        automation.current().task_failure_notifier = failure_notifier
        automation.current().task_error_notifier = error_notifier
        automation.current().task_end_notifier = end_notifier

    This is handy for testing and debugging, when more in-depth notifications are needed, since a
    lot of normally unnecessary notifications can be turned on/off with a single switch.
    """

    def __init__(self, description, start_notifier=NotImplemented, success_notifier=NotImplemented,
                 failure_notifier=NotImplemented, error_notifier=NotImplemented,
                 end_notifier=NotImplemented):
        verify_type(description, str, non_empty=True)

        self._description = description

        context = auto_context.current()

        if context is not None:
            assert isinstance(context, auto_context)
            self.start_notifier = context.task_start_notifier
            self.success_notifier = context.task_success_notifier
            self.failure_notifier = context.task_failure_notifier
            self.error_notifier = context.task_error_notifier
            self.end_notifier = context.task_end_notifier
        else:
            self.start_notifier = None
            self.success_notifier = None
            self.failure_notifier = None
            self.error_notifier = None
            self.end_notifier = None

        if start_notifier is not NotImplemented:
            self.start_notifier = start_notifier
        if success_notifier is not NotImplemented:
            self.success_notifier = success_notifier
        if failure_notifier is not NotImplemented:
            self.failure_notifier = failure_notifier
        if error_notifier is not NotImplemented:
            self.error_notifier = error_notifier
        if end_notifier is not NotImplemented:
            self.end_notifier = end_notifier

        verify_callable(self.start_notifier, allow_none=True)
        verify_callable(self.success_notifier, allow_none=True)
        verify_callable(self.failure_notifier, allow_none=True)
        verify_callable(self.error_notifier, allow_none=True)
        verify_callable(self.end_notifier, allow_none=True)

        self._started = None
        self._ended = None
        self._successful = None
        self._message = None

    @property
    def description(self):
        """The description of the task."""
        return self._description

    @property
    def started(self):
        """The time when the task was started."""
        return self._started

    @property
    def in_progress(self):
        """Whether the task is currently in progress."""
        return self._started is not None and self._ended is None

    @property
    def ended(self):
        """The time when the task ended."""
        return self._ended

    @property
    def successful(self):
        """Whether the task was successful."""
        return self._successful

    @property
    def message(self):
        """The success or failure message."""
        return self._message

    def success(self, message=None):
        """Notify that the task succeeded."""
        verify_type(message, str, non_empty=True, allow_none=True)
        assert self._successful is None
        if message is None:
            message = 'Completed successfully.'
        self._successful = True
        self._message = message
        if self.success_notifier is not None:
            self.success_notifier(
                **notification_parameters(
                    SUCCESS_EVENT,
                    self._description,
                    message
                )
            )

    def failure(self, message=None):
        """Notify that the task failed."""
        verify_type(message, str, non_empty=True, allow_none=True)
        assert self._successful is None
        if message is None:
            message = 'Task failed.'
        self._successful = False
        self._message = message
        if self.failure_notifier is not None:
            self.failure_notifier(
                **notification_parameters(
                    FAILURE_EVENT,
                    self._description,
                    message
                )
            )

    def __enter__(self):
        self._started = datetime.datetime.now()
        if self.start_notifier is not None:
            self.start_notifier(
                **notification_parameters(
                    START_EVENT,
                    self._description,
                    time=self._started
                )
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ended = datetime.datetime.now()
        exception_occurred = exc_type or exc_val or exc_tb
        if self.error_notifier is not None and exception_occurred:
            self.error_notifier(
                **notification_parameters(
                    EXCEPTION_EVENT,
                    self._description,
                    exc_info=(exc_type, exc_val, exc_tb),
                    time=self._ended
                )
            )
        if self._successful is None:
            if exception_occurred:
                self.failure('Failed due to unhandled exception.')
            else:
                self.success()
        if self.end_notifier is not None:
            self.end_notifier(
                **notification_parameters(
                    END_EVENT,
                    self._description,
                    time=self._ended
                )
            )
        return False  # Indicates exceptions should NOT be suppressed.


class auto_context:
    """
    Interface for automation processes to access environment and configuration settings.
    """

    _THREAD_LOCAL = threading.local()

    @classmethod
    def _get_stack(cls):
        stack = getattr(cls._THREAD_LOCAL, 'stack', None)
        if stack is None:
            stack = []
            cls._THREAD_LOCAL.stack = stack
        return stack

    @classmethod
    def root(cls, default=None):
        """Get the root automation context for this thread."""
        stack = cls._get_stack()
        if stack:
            return stack[0]
        return default

    @classmethod
    def current(cls, default=None):
        """Get the current automation context for this thread."""
        stack = cls._get_stack()
        if stack:
            return stack[-1]
        return default

    def __init__(self, name=None, version=None, manager=None, start_time=None, testing=False):
        if start_time is None:
            start_time = datetime.datetime.now()
        verify_type(start_time, datetime.datetime)

        verify_type(testing, bool)

        if not name:
            name = get_entry_point_name('UNKNOWN')
        verify_type(name, str, non_empty=True)

        if not version:
            version = get_entry_point_version()

        shared_manager = get_automation_config_manager()
        fallbacks = [shared_manager]

        # Combine the config loaders into a default hierarchy.
        if manager is None:
            manager = ConfigManager(name, fallbacks=fallbacks)
        elif not isinstance(manager, ConfigManager):
            manager = ConfigManager(manager, fallbacks=fallbacks)
        else:
            fallbacks.insert(0, manager)
            manager = ConfigManager(name, fallbacks=fallbacks)
        verify_type(manager, ConfigManager)

        automation_root = shared_manager.load_option(
            'Environment',
            'Automation Root',
            Path,
            default=Path('~/.automation')
        )
        assert isinstance(automation_root, Path)
        assert automation_root.is_local

        manager.set_option('Environment', 'Automation Name', name)

        root_dir = manager.load_option('Environment', 'Root Path', Path,
                                       default=automation_root / name)

        workspace_dir = manager.load_option('Environment', 'Workspace Folder Path', Path,
                                            default=root_dir / 'workspace')
        log_dir = manager.load_option('Environment', 'Log Folder Path', Path,
                                      default=root_dir / 'logs')
        docs_dir = manager.load_option('Environment', 'Documentation Folder Path', Path,
                                       default=root_dir / 'docs')
        data_dir = manager.load_option('Environment', 'Data Folder Path', Path,
                                       default=root_dir / 'data')

        loggers = manager.load_option('Environment', 'Loggers', 'list', None)
        verify_type(loggers, list, allow_none=True)

        testing = manager.load_option('Environment', 'Testing', 'bool', testing)
        verify_type(testing, bool)

        if loggers is None:
            logging.basicConfig()
        else:
            for index, logger_name in enumerate(loggers):
                logger = manager.load_section(logger_name, Logger)
                verify_type(logger, logging.Logger)

        # Start of automation
        automation_start_notifier = manager.load_option('Environment', 'On Automation Start', default=None)
        verify_callable(automation_start_notifier, allow_none=True)

        # Error (not necessarily terminated or a failure)
        automation_error_notifier = manager.load_option('Environment', 'On Automation Error', default=None)
        verify_callable(automation_error_notifier, allow_none=True)

        # End of automation
        automation_end_notifier = manager.load_option('Environment', 'On Automation End', default=None)
        verify_callable(automation_end_notifier, allow_none=True)

        # Start of task
        task_start_notifier = manager.load_option('Environment', 'On Task Start', default=None)
        verify_callable(task_start_notifier, allow_none=True)

        # Task completed successfully (not necessarily terminated)
        task_success_notifier = manager.load_option('Environment', 'On Task Success', default=None)
        verify_callable(task_success_notifier, allow_none=True)

        # Task failure (not necessarily terminated or an error)
        task_failure_notifier = manager.load_option('Environment', 'On Task Failure', default=None)
        verify_callable(task_failure_notifier, allow_none=True)

        # Error (not necessarily terminated or a failure)
        task_error_notifier = manager.load_option('Environment', 'On Task Error', default=None)
        verify_callable(automation_error_notifier, allow_none=True)

        # Task failure (not necessarily terminated or an error)
        task_end_notifier = manager.load_option('Environment', 'On Task End', default=None)
        verify_callable(task_end_notifier, allow_none=True)

        self._automation_root = automation_root

        self._name = name
        self._version = version
        self._manager = manager
        self._start_time = start_time
        self._testing = testing

        self._root_dir = root_dir
        self._workspace = workspace_dir
        self._log_dir = log_dir
        self._docs_dir = docs_dir
        self._data_dir = data_dir

        # self._log_file_path = log_file_path
        # self._log_entry_format = log_entry_format
        # self._log_level = log_level

        self._automation_start_notifier = automation_start_notifier
        self._automation_error_notifier = automation_error_notifier
        self._automation_end_notifier = automation_end_notifier

        self._task_start_notifier = task_start_notifier
        self._task_success_notifier = task_success_notifier
        self._task_failure_notifier = task_failure_notifier
        self._task_error_notifier = task_error_notifier
        self._task_end_notifier = task_end_notifier

        for path in workspace_dir, log_dir, docs_dir, data_dir:
            assert isinstance(path, Path)
            if not path.is_dir:
                path.make_dir()

    def post_install_hook(self, overwrite=False):
        """
        This is called by attila.installation.setup() after installation completes, which gives the
        automation the opportunity to install its config and data files in the appropriate location
        based on the local attila installation's configuration.
        """

        # TODO: This is broken; it finds the version at preferred_config_path instead of the one
        #       inside the folder in site-packages, which basically means it tries to copy the old
        #       file over itself if overwrite is set.
        current_config_path = last(iter_config_search_paths(self._name), None)
        if current_config_path is None:
            warnings.warn("Config file not found.")
            return

        current_config_path = Path(current_config_path)
        current_config_path.verify_is_file()

        preferred_config_path = self._manager.load_option(
            'Environment',
            'Preferred Config Path',
            Path,
            default=self._root_dir / (self._name + '.ini')
        )
        assert isinstance(preferred_config_path, Path)

        if not overwrite and preferred_config_path.is_file:
            warnings.warn(("The configuration file %s already exists. If you wish to update it, "
                           "you must either update the config file manually, or import the module "
                           "and call %s.main.context.post_install_hook(overwrite=True) to "
                           "overwrite it.") %
                          (abs(preferred_config_path), self._name))
        else:
            current_config_path.copy_to(preferred_config_path, overwrite)

    @property
    def automation_root(self):
        """
        The root folder for all automations.

        :return: A Path instance.
        """
        return self._automation_root

    @property
    def name(self):
        """
        The name of the automation.

        :return: A non-empty str instance.
        """
        return self._name

    @property
    def version(self):
        """
        The version of the automation.

        :return: A non-empty str instance, or None.
        """
        return self._version

    @property
    def manager(self):
        """
        The config manager for this automation's settings.

        :return: A ConfigManager instance.
        """
        return self._manager

    @property
    def testing(self):
        """
        Whether the automation is executing in test mode.

        :return: A bool value.
        """
        return self._testing

    @property
    def root_dir(self):
        """
        The root directory where this automation's files are housed.

        :return: A Path instance.
        """
        return self._root_dir

    @property
    def workspace(self):
        """
        The directory the automation should use for performing file operations and storing
        persistent state.

        :return: A Path instance.
        """
        return self._workspace

    @property
    def log_dir(self):
        """
        The directory the automation should use for log files.

        :return: A Path instance.
        """
        return self._log_dir

    # @property
    # def log_file_path(self):
    #     """
    #     The path to the log file the automation should log to.
    #
    #     :return: A Path instance.
    #     """
    #     return self._log_file_path
    #
    # @property
    # def log_entry_format(self):
    #     """
    #     The log format the automation should use.
    #
    #     :return: A string.
    #     """
    #     return self._log_entry_format
    #
    # @property
    # def log_level(self):
    #     """
    #     The log level the automation should use.
    #
    #     :return: An integer.
    #     """
    #     return self._log_level

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
    def automation_start_notifier(self):
        """
        Use this notifier at the start of the automation's execution.

        :return: A Notifier instance.
        """
        return self._automation_start_notifier

    @property
    def automation_error_notifier(self):
        """
        Use this notifier for reporting errors.

        :return: A Notifier instance.
        """
        return self._automation_error_notifier

    @property
    def automation_end_notifier(self):
        """
        Use this notifier at the end of the automation's execution, regardless of whether any
        errors or failures occurred.

        :return: A Notifier instance.
        """
        return self._automation_end_notifier

    @property
    def task_start_notifier(self):
        """
        Use this notifier when entering the context of a task.

        :return: A Notifier instance.
        """
        return self._task_success_notifier

    @property
    def task_success_notifier(self):
        """
        Use this notifier when leaving the context of a task that has been marked as a success.

        :return: A Notifier instance.
        """
        return self._task_success_notifier

    @property
    def task_failure_notifier(self):
        """
        Use this notifier when leaving the context of a task that has been marked as a failure.

        :return: A Notifier instance.
        """
        return self._task_failure_notifier

    @property
    def task_error_notifier(self):
        """
        Use this notifier when an unhandled exception causes the context of a task to be left.

        :return: A Notifier instance.
        """
        return self._task_error_notifier

    @property
    def task_end_notifier(self):
        """
        Use this notifier when leaving the context of a task under any conditions.

        :return: A Notifier instance.
        """
        return self._task_failure_notifier

    def __enter__(self):
        self._get_stack().append(self)
        if self._automation_start_notifier is not None:
            self._automation_start_notifier(
                **notification_parameters(
                    START_EVENT,
                    time=self._start_time
                )
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        traceback_string = None

        if exc_tb and (self._automation_error_notifier or self._automation_end_notifier):
            traceback_string = traceback.format_exc()

        if self._automation_error_notifier is not None and (exc_type or exc_val or exc_tb):
            # TODO: Add a way to specify ignored errors, either in this class or in the notifiers,
            #       so we have a way to turn off BdbQuit and SystemExit spam. This should really
            #       only be done for emails, not for database, log, or other impersonal reporting,
            #       so I suspect it will need to be done at the notifier level, not here.
            self._automation_error_notifier(
                **notification_parameters(
                    EXCEPTION_EVENT,
                    exc_info=(exc_type, exc_val, exc_tb)
                )
            )

        if self._automation_end_notifier is not None:
            self._automation_end_notifier(**notification_parameters(END_EVENT))

        self._get_stack().pop()
        return False  # Do not suppress exceptions.

    def __call__(self, function):
        verify_callable(function)

        @wraps(function)
        def wrapper(*args, **kwargs):
            """Wraps the function so that the automation context is automatically entered for the
            duration of each call to the function."""
            with self:
                return function(*args, **kwargs)

        wrapper.context = self

        return wrapper


def automation(name=None, manager=None, start_time=None):
    """
    Decorator for wrapping main() in an automation context.

    :param name: The name of the automation.
    :param manager: The configuration manager.
    :param start_time: The time the automation started.
    :return: An automation context decorator.
    """
    if callable(name):
        function = name
        assert manager is None and start_time is None
        context = auto_context()
        return context(function)
    else:
        return auto_context(name, manager, start_time)
