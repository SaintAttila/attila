from distutils.util import strtobool


from ..abc.configurations import Configurable
from ..abc.files import Path
from ..abc.notifications import Notifier
from ..configurations import ConfigLoader
from ..exceptions import OperationNotSupportedError, verify_type

__author__ = 'Aaron Hosford'


# TODO: Should this inherit from connection?
class FileNotifier(Notifier, Configurable):
    """
    A file notifier passes incoming notifications to an arbitrary file.
    """

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param config_loader: A ConfigLoader instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(config_loader, ConfigLoader)
        assert isinstance(config_loader, ConfigLoader)
        verify_type(value, str, non_empty=True)

        path = Path.load_config_value(config_loader, value)
        assert isinstance(path, Path)

        return cls(*args, path=path, **kwargs)

    @classmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a class instance from a config section.

        :param config_loader: A ConfigLoader instance.
        :param section: The name of the section.
        :return: A new instance of this class.
        """
        verify_type(config_loader, ConfigLoader)
        assert isinstance(config_loader, ConfigLoader)
        verify_type(section, str, non_empty=True)

        path = config_loader.load_option(section, 'Path', Path, None)
        if path is None:
            path = config_loader.load_section(section, Path)
        assert isinstance(path, Path)

        append = config_loader.load_option(section, 'Append', strtobool, True)

        format_string = config_loader.load_option(section, 'Format', str, None)
        if format_string is None:
            format_path = config_loader.load_option(section, 'Format Path', Path, None)
            if format_path is not None:
                assert isinstance(format_path, Path)
                with format_path.open():
                    format_string = format_path.read()

        encoding = config_loader.load_option(section, 'Encoding', str, None)

        return cls(*args, path=path, append=append, format_string=format_string, encoding=encoding, **kwargs)

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

    def send(self, *args, attachments=None, **kwargs):
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
        self._file_obj.close()
