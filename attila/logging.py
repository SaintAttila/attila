import logging
import logging.handlers

from abc import ABCMeta

from attila.abc.configurations import Configurable
from attila.abc.files import Path
from attila.configurations import ConfigManager, config_loader
from attila.exceptions import OperationNotSupportedError, verify_type
from attila.strings import split_port


__author__ = 'Aaron Hosford'


# See https://docs.python.org/2/library/logging.config.html#logging.config.fileConfig


class LogHandler(Configurable, metaclass=ABCMeta):

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

        format = manager.load_option(section, 'Format', LogFormat, None)
        verify_type(format, LogFormat, allow_none=True)
        if format is None:
            format = LogFormat()

        level = manager.load_option(section, 'Level', 'log_level', logging.INFO)

        result = cls(*args, **kwargs)

        result.formatter = format
        result.level = level

        return result


@config_loader
class LogFileHandler(LogHandler, logging.FileHandler):

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(value, str, non_empty=True)
        path = Path.load_config_value(manager, value, *args, **kwargs)
        return cls(*args, filename=str(abs(path)), **kwargs)

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

        path = manager.load_option(section, 'Path', Path)
        mode = manager.load_option(section, 'Mode', str, 'a')
        encoding = manager.load_option(section, 'Encoding', str, None)
        delay = manager.load_option(section, 'Delay', 'bool', False)

        return super().load_config_section(
            manager,
            section,
            *args,
            filename=str(abs(path)),
            mode=mode,
            encoding=encoding,
            delay=delay,
            **kwargs
        )

    def __init__(self, filename, mode='a', encoding=None, delay=False):
        Configurable.__init__(self)
        logging.FileHandler.__init__(self, filename, mode, encoding, delay)


@config_loader
class LogSocketHandler(LogHandler, logging.handlers.SocketHandler):

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(value, str, non_empty=True)

        host, port = split_port(value, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
        verify_type(host, str, non_empty=True)

        return cls(*args, host=host, port=port, **kwargs)

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

        host = manager.load_option(section, 'Host', str)
        verify_type(host, str, non_empty=True)

        host, port = split_port(host, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
        verify_type(host, str, non_empty=True)

        return super().load_config_section(
            manager,
            section,
            *args,
            host=host,
            port=port,
            **kwargs
        )

    def __init__(self, host, port):
        Configurable.__init__(self)
        logging.handlers.SocketHandler.__init__(self, host, port)


# TODO: Wrap the other handlers defined in the built-in logging module.
# TODO: Wrap filters and allow them to be set.


@config_loader
class LogFormat(Configurable, logging.Formatter):

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(value, str, non_empty=True)

        return cls(*args, fmt=value, **kwargs)

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

        format_string = manager.load_option(section, 'Format', str, None)
        date_format = manager.load_option(section, 'Date Format', str, None)
        style = manager.load_option(section, 'Style', str, '%')

        return cls(
            *args,
            fmt=format_string,
            datefmt=date_format,
            style=style,
            **kwargs
        )

    def __init__(self, fmt=None, datefmt=None, style='%'):
        Configurable.__init__(self)
        logging.Formatter.__init__(self, fmt, datefmt, style)


@config_loader
class Logger(Configurable, logging.Logger):

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        raise OperationNotSupportedError()

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
        verify_type(name, str, non_empty=True)

        level = manager.load_option(section, 'Level', 'log_level', logging.NOTSET)

        handlers = manager.load_option(section, 'Handlers', 'list')
        for index, handler_name in enumerate(handlers):
            handler = manager.load_section(handler_name)
            verify_type(handler, LogHandler)
            handlers[index] = handler

        if name == 'root':
            result = logging.root
        else:
            result = logging.getLogger(name)
            propagate = manager.load_option(section, 'Propagate', 'bool', True)
            result.propagate = propagate

        result.level = level

        for handler in handlers:
            result.addHandler(handler)

        return result

    def __init__(self, name, level=logging.NOTSET):
        Configurable.__init__(self)
        logging.Logger.__init__(self, name, level)
