"""
Bindings for sending notifications to Python logger objects.
"""


import logging


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier
from ..configurations import ConfigManager
from ..exceptions import OperationNotSupportedError, verify_type
from ..plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'LogNotifier',
]


@config_loader
class LogNotifier(Notifier, Configurable):
    """
    A log notifier passes incoming notifications to a logger.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(manager, ConfigManager)
        verify_type(value, str, non_empty=True)

        if ':' in value:
            index = value.index(':')
            name_level = value[:index]
            msg = value[index + 1:]
        else:
            name_level = value
            msg = None

        if '@' in name_level:
            name, level = name_level.split('@')
            if level.isdigit():
                level = int(level)
            else:
                level = getattr(logging, level.upper())
                assert isinstance(level, int)
        else:
            name = name_level
            level = logging.INFO

        if not name or name.lower() == 'root':
            logger = logging.root
        else:
            logger = logging.getLogger(name)

        return cls(*args, logger=logger, level=level, msg=msg, **kwargs)

    @classmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a class instance from a config section.

        :param manager: A ConfigManager instance.
        :param section: The name of the section.
        :return: A new instance of this class.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)
        verify_type(section, str, non_empty=True)

        name = manager.load_option(section, 'Name', str)
        level = manager.load_option(section, 'Level', 'log_level', logging.INFO)
        msg = manager.load_option(section, 'Message', str, None)

        if not name or name.lower() == 'root':
            logger = logging.root
        else:
            logger = logging.getLogger(name)

        return cls(*args, logger=logger, level=level, msg=msg, **kwargs)

    def __init__(self, logger, level=None, msg=None):
        if isinstance(logger, str):
            verify_type(logger, str, non_empty=True)
            logger = logging.getLogger(logger)
        verify_type(logger, logging.Logger)

        if level is None:
            level = logging.INFO
        verify_type(level, int)

        verify_type(msg, str, allow_none=True)

        super().__init__()

        self._logger = logger
        self._level = level
        self._msg = msg

    @property
    def logger(self):
        """The logger this notifier sends to."""
        return self._logger

    @property
    def level(self):
        """The logging level this notifier sends at."""
        return self._level

    @property
    def msg(self):
        """The log message template, if any."""
        return self._msg

    def __call__(self, msg=None, attachments=None, **kwargs):
        """
        Send a notification on this notifier's channel.

        :param attachments: The file attachments, if any, to include in the notification. (Not
            supported.)
        :return: None
        """
        if self._logger.level > self._level:
            return  # It's a no-op, so skip the time it would take to do arg checking & formatting
        if attachments is not None:
            raise OperationNotSupportedError("File attachments are unsupported.")

        # Interpolate keyword arguments
        if msg is None:
            if self._msg is None:
                msg = str(kwargs)
            else:
                msg = self._msg.format_map(kwargs)
        else:
            verify_type(msg, str)
            msg.format_map(kwargs)

        # Extract arguments that the logger itself accepts.
        log_args = {}
        for name in ('exc_info', 'stack_info', 'extra'):
            if name == 'exc_info' and kwargs.get(name, None) in (None, (None, None, None)):
                continue
            if name in kwargs:
                log_args[name] = kwargs[name]

        self._logger.log(self._level, msg, **log_args)
