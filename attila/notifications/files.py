"""
attila.notifications.files
==========================

Bindings for sending notifications to file objects.
"""


from distutils.util import strtobool


from ..abc.configurations import Configurable
from ..abc.files import Path
from ..abc.notifications import Notifier
from ..configurations import ConfigManager
from ..exceptions import OperationNotSupportedError, verify_type
from ..plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'FileNotifier',
]


# TODO: Should this inherit from connection?
@config_loader
class FileNotifier(Notifier, Configurable):
    """
    A file notifier passes incoming notifications to an arbitrary file.
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
        assert isinstance(manager, ConfigManager)
        verify_type(value, str, non_empty=True)

        path = Path.load_config_value(manager, value)
        assert isinstance(path, Path)

        return cls(*args, path=path, **kwargs)

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

        path = manager.load_option(section, 'Path', Path, None)
        if path is None:
            path = manager.load_section(section, Path)
        assert isinstance(path, Path)

        append = manager.load_option(section, 'Append', strtobool, True)

        format_string = manager.load_option(section, 'Format', str, None)
        if format_string is None:
            format_path = manager.load_option(section, 'Format Path', Path, None)
            if format_path is not None:
                assert isinstance(format_path, Path)
                with format_path.open():
                    format_string = format_path.read()

        encoding = manager.load_option(section, 'Encoding', str, None)

        return cls(
            *args,
            path=path,
            append=append,
            format_string=format_string,
            encoding=encoding,
            **kwargs
        )

    def __init__(self, path=None, append=True, format_string=None, encoding=None):
        verify_type(append, bool)
        if format_string is not None:
            verify_type(format_string, str)
        if encoding is not None:
            verify_type(encoding, str)

        if isinstance(path, str):
            path = Path(path)
            file_obj = path.open(mode=('a' if append else 'w'), encoding=encoding)
        elif isinstance(path, Path):
            file_obj = path.open(mode=('a' if append else 'w'), encoding=encoding)
        else:
            file_obj = path
            assert hasattr(file_obj, 'write')

        super().__init__()

        self._format_string = format_string
        self._file_obj = file_obj

    def __call__(self, *args, attachments=None, **kwargs):
        """
        Send a notification on this notifier's channel.

        :param attachments: The file attachments, if any, to include in the notification.
        :return: None
        """
        if attachments is not None:
            raise OperationNotSupportedError("File attachments are unsupported.")
        if self._format_string is None:
            print(*args, file=self._file_obj, **kwargs)
        else:
            self._file_obj.write(self._format_string.format(*args, **kwargs))

    def close(self):
        """Close the file notifier, and its associated file."""
        self._file_obj.close()
