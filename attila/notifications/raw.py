import configparser
import datetime
import keyword
import logging
import sys

from abc import ABCMeta


from ..abc.notifications import Channel, Notification, Notifier


__all__ = [
    'RawChannel',
    'RawNotification',
    'RawNotifier',
    'FileChannel',
    'LogChannel',
    'CallbackChannel',
]


class RawChannel(Channel, metaclass=ABCMeta):
    pass


class RawNotification(Notification):

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs


class RawNotifier(Notifier):

    def __init__(self, channel):
        assert isinstance(channel, RawChannel)
        super().__init__(channel)

    def build_notification(self, *args, **kwargs):
        """
        Construct a raw notification from the arguments passed to the send() method.
        """
        return RawNotification(*args, **kwargs)


class FileChannel(RawChannel):

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        file = datetime.datetime.now().strftime(config[section]['File'])
        append = config.getboolean(section, 'Append', fallback=True)
        format_string = config[section].get('Format')
        encoding = config[section].get('Encoding', 'utf-8')
        return cls(file, append, format_string, encoding)

    def __init__(self, file, append=True, format_string=None, encoding=None):
        assert isinstance(file, str)
        assert append == bool(append)
        assert format_string is None or isinstance(format_string, str)
        assert encoding is None or isinstance(encoding, str)

        self._file = file
        self._append = bool(append)
        self._format_string = format_string
        self._encoding = encoding

        if file.lower() in ('stdout', 'stderr'):
            assert append
            assert encoding is None
            self._file_obj = getattr(sys, file.lower())
        else:
            self._file_obj = open(file, mode=('a' if append else 'w'), encoding=encoding)

    def send(self, notification):
        assert isinstance(notification, RawNotification)
        if self._format_string is None:
            print(*notification.args, file=self._file_obj, **notification.kwargs)
        else:
            self._file_obj.write(self._format_string.format(*notification.args, **notification.kwargs))

    def close(self):
        self._file_obj.close()


class LogChannel(RawChannel):

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        logger_name = config[section]['Name']
        logger = logging.getLogger(logger_name)
        level = config.getint(section, 'Level', fallback=logging.INFO)
        return cls(logger, level)

    def __init__(self, logger, level=logging.INFO):
        assert isinstance(logger, logging.Logger)
        assert isinstance(level, int)  # Log levels are always integers.
        self._logger = logger
        self._level = level

    @property
    def logger(self):
        return self._logger

    @property
    def level(self):
        return self._level

    def send(self, notification):
        assert isinstance(notification, RawNotification)
        self._logger.log(self._level, *notification.args, **notification.kwargs)


class CallbackChannel(RawChannel):
    """
    A callback channel passes incoming notifications to an arbitrary Python callback. It allows us to wrap Python
    functions in the notification channel interface so we can easily interchange them.
    """

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        config_section = config[section]
        function = config_section['Function']
        assert all(char.isalnum() or char in ('.', '_') for char in function)
        assert not any(keyword.iskeyword(piece) for piece in function.split('.'))
        function = eval(function)
        assert callable(function)
        return cls(function)

    def __init__(self, callback):
        assert callable(callback)
        self._callback = callback

    @property
    def callback(self):
        return self._callback

    def send(self, notification):
        assert isinstance(notification, RawNotification)
        self._callback(*notification.args, **notification.kwargs)