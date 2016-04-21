"""
attila.env
==========

A standardized automation environment
"""

import configparser
import datetime
import inspect
import logging
import threading

from functools import wraps


from .abc.files import Path

from .configurations import get_automation_config_loader, ConfigLoader
from .exceptions import verify_type, verify_callable


__all__ = [
    'get_entry_point_name',
    'task',
    'automation',
]


def get_entry_point_name(default=None):
    """
    Locate the module closest to where execution began and return its name. If no module could be
    identified (which can sometimes occur when running from some IDEs when a module is run without
    being saved first), returns default.

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


class task:
    """
    Use with the 'with' statement to automatically track what task is being performed.

    Example Usage:
        with task("Doing stuff...") as root_task:
            print("Now I'm doing stuff.")

            with task("Doing more detailed stuff...") as subtask:
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

        context = automation.current()

        if context is not None:
            assert isinstance(context, automation)
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
                task=self.description,
                event='success',
                time=datetime.datetime.now(),
                message=message
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
                task=self.description,
                event='failure',
                time=self._ended,
                message=message
            )

    def __enter__(self):
        self._started = datetime.datetime.now()
        if self.start_notifier is not None:
            self.start_notifier(
                task=self.description,
                event='start',
                time=self._started
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._ended = datetime.datetime.now()
        exception_occurred = exc_type or exc_val or exc_tb
        if self.error_notifier is not None and exception_occurred:
            self.error_notifier(
                task=self.description,
                event='exception',
                time=self._ended,
                exc_info=(exc_type, exc_val, exc_tb)
            )
        if self._successful is None:
            if exception_occurred:
                self.failure('Failed due to unhandled exception.')
            else:
                self.success()
        if self.end_notifier is not None:
            self.end_notifier(
                task=self.description,
                event='end',
                time=self._ended
            )
        return False  # Indicates exceptions should NOT be suppressed.


class automation:
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

    def __init__(self, name=None, config_loader=None, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        verify_type(start_time, datetime.datetime)

        if not name:
            name = get_entry_point_name('UNKNOWN')
        verify_type(name, str, non_empty=True)

        if config_loader is None:
            local_config_loader = ConfigLoader(name)
        elif not isinstance(config_loader, ConfigLoader):
            local_config_loader = ConfigLoader(config_loader)
        else:
            local_config_loader = config_loader
        verify_type(local_config_loader, ConfigLoader)

        shared_config_loader = get_automation_config_loader()

        # Combine the config loaders into a default hierarchy.
        config_loader = ConfigLoader(
            configparser.ConfigParser(),
            fallbacks=[local_config_loader, shared_config_loader]
        )

        root_dir = config_loader.load_option('Environment', 'Root Path', Path, 
                                             default=Path('~/.automation'))

        workspace_dir = config_loader.load_option('Environment', 'Workspace Folder Path', Path,
                                                  default=root_dir['workspace'][name])
        log_dir = config_loader.load_option('Environment', 'Log Folder Path', Path,
                                            default=root_dir['logs'][name])
        docs_dir = config_loader.load_option('Environment', 'Documentation Folder Path', Path,
                                             default=root_dir['docs'][name])
        data_dir = config_loader.load_option('Environment', 'Data Folder Path', Path,
                                             default=root_dir['data'][name])

        log_file_name_template = config_loader.load_option(
            'Environment',
            'Log File Name Template',
            str,
            default='%Y%m%d%H%M%S.log'
        )
        log_entry_format = config_loader.load('Environment', 'Log Entry Format', str,
                                              default='%(asctime)s_pid:%(process)d ~*~ %(message)s')
        log_level = config_loader.load('Environment', 'Log Level', str,
                                       default='INFO')

        log_file_name = start_time.strftime(log_file_name_template)
        log_file_path = log_dir[log_file_name]

        if log_level.isdigit():
            log_level = int(log_level)
        else:
            log_level = getattr(logging, log_level.upper())
        verify_type(log_level, int)

        # Start of automation
        automation_start_notifier = \
            config_loader.load_option('Environment', 'Automation Start Notifier')
        verify_callable(automation_start_notifier)

        # Error (not necessarily terminated or a failure)
        automation_error_notifier = \
            config_loader.load_option('Environment', 'Automation Error Notifier')
        verify_callable(automation_error_notifier)

        # End of automation
        automation_end_notifier = \
            config_loader.load_option('Environment', 'Automation End Notifier')
        verify_callable(automation_end_notifier)

        # Start of task
        task_start_notifier = config_loader.load_option('Environment', 'Task Start Notifier')
        verify_callable(task_start_notifier)

        # Task completed successfully (not necessarily terminated)
        task_success_notifier = config_loader.load_option('Environment', 'Task Success Notifier')
        verify_callable(task_success_notifier)

        # Task failure (not necessarily terminated or an error)
        task_failure_notifier = config_loader.load_option('Environment', 'Task Failure Notifier')
        verify_callable(task_failure_notifier)

        # Error (not necessarily terminated or a failure)
        task_error_notifier = config_loader.load_option('Environment', 'Task Error Notifier')
        verify_callable(automation_error_notifier)

        # Task failure (not necessarily terminated or an error)
        task_end_notifier = config_loader.load_option('Environment', 'Task End Notifier')
        verify_callable(task_end_notifier)

        self._name = name
        self._config_loader = config_loader

        self._workspace = workspace_dir
        self._log_dir = log_dir
        self._docs_dir = docs_dir
        self._data_dir = data_dir

        self._log_file_path = log_file_path
        self._log_entry_format = log_entry_format

        self._automation_start_notifier = automation_start_notifier
        self._automation_error_notifier = automation_error_notifier
        self._automation_end_notifier = automation_end_notifier

        self._task_start_notifier = task_start_notifier
        self._task_success_notifier = task_success_notifier
        self._task_failure_notifier = task_failure_notifier
        self._task_error_notifier = task_error_notifier
        self._task_end_notifier = task_end_notifier

    @property
    def name(self):
        """
        The name of the automation.

        :return: A non-empty str instance.
        """
        return self._name

    @property
    def config_loader(self):
        """
        The config loader for this automation's settings.

        :return: A ConfigLoader instance.
        """
        return self._config_loader

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

    @property
    def log_file_path(self):
        """
        The path to the log file the automation should log to.

        :return: A Path instance.
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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type or exc_val or exc_tb:
            self._automation_error_notifier(exc_type, exc_val, exc_tb)
        self.automation_end_notifier()
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

        return wrapper
