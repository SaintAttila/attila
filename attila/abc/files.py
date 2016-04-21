"""
attila.abc.files
================

Interface definition for paths, file system connectors, and file system connections.
"""


import csv
import datetime
import logging
import os
import time

from abc import ABCMeta, abstractmethod

from .configurations import Configurable
from .connections import Connector, connection

from .. import configurations
from ..exceptions import NoDefaultFSConnectionError, OperationNotSupportedError, verify_type


__all__ = [
    'Path',
    'FSConnector',
    'fs_connection',
]


log = logging.getLogger(__name__)


FORM_FEED_CHAR = '\x0C'


# TODO: Use this to make path operations that affect multiple files/folders into atomic operations.
#       The idea is to record everything that has done and, using temp files, make all operations
#       reversible. If an error occurs partway through the transaction, the temp files are then
#       used to roll back the operations performed so far. Otherwise, when all operations have been
#       completed, the temp files are destroyed. Once this class is finished, we can add an
#       "atomic" flag as a parameter to each of the multi-operation methods of Path, which enables
#       the use of transactions.
# class PathTransaction:
#
#     def __init__(self):
#         self._operations = []
#
#     def commit(self):
#         for operation in self._operations:


class temp_cwd:
    """
    This class just temporarily changes the working directory of a file system connection, and then
    changes it back. It's meant for use in a with statement. It only exists to allow Paths to be
    used as 'with' contexts. It is not meant to be a part of this module's public interface.
    """

    def __init__(self, path):
        assert isinstance(path, Path)
        self._path = path
        self._previous_path = None

    def __enter__(self):
        self._previous_path = None
        if self._path:
            previous_path = self._path.connection.cwd
            self._previous_path = previous_path
            self._path.connection.cwd = self._path
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._previous_path is not None:
            self._path.connection.cwd = self._previous_path
            self._previous_path = None
        return False  # Do not suppress exceptions.


class Path(Configurable):
    """
    A Path consists of a string representing a location, together with a connection that indicates
    the object responsible for interfacing with the underlying file system on behalf of the path.
    """

    _default_connection = None

    @classmethod
    def get_default_connection(cls):
        """
        Get the default file system connection used when a new Path is instantiated.
        """
        return cls._default_connection

    # noinspection PyShadowingNames
    @classmethod
    def set_default_connection(cls, connection):
        """
        Set the default file system connection used when a new Path is instantiated.

        :param connection: The new default file system connection.
        """
        assert connection is None or isinstance(connection, fs_connection)
        cls._default_connection = connection

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param config_loader: A ConfigLoader instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        return config_loader.load_path(value)

    @classmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a class instance from a config section.

        :param config_loader: A ConfigLoader instance.
        :param section: The name of the section.
        :return: A new instance of this class.
        """
        verify_type(config_loader, configurations.ConfigLoader)
        assert isinstance(config_loader, configurations.ConfigLoader)

        loc = datetime.datetime.now().strftime(config_loader.load_option(section, 'Location', str))

        con = config_loader.load_option(section, 'Connection', default=None)
        if con is None:
            # If there is no such option, try to load this section as a connection instead.
            con = config_loader.load_section(section)
        elif isinstance(con, str):
            # Treat it as a partial URL.
            path = cls.load_config_value(config_loader, con)
            assert not str(path)
            con = path.connection

        if con is not None:
            if isinstance(con, FSConnector):
                # If it's a connector, create a connection from it.
                con = con.connect()
            verify_type(con, fs_connection)

        return cls(*args, location=loc, connection=con, **kwargs)

    # noinspection PyShadowingNames
    def __init__(self, location='', connection=None):
        if isinstance(location, Path):
            path = location
            location = path._location
            connection = connection or path.connection

        if connection is None:
            connection = self.get_default_connection()
            if connection is None:
                raise NoDefaultFSConnectionError("No default connection has been set.")

        verify_type(location, str)
        verify_type(connection, fs_connection)

        self._location = location
        self._connection = connection

    def copy(self):
        """
        Create a copy of this path.

        :return: A new Path instance.
        """
        return type(self)(self._location, self._connection)

    @property
    def connection(self):
        """The connection this path is accessed through."""
        return self._connection

    def __bool__(self):
        return bool(self._location)

    def __enter__(self):
        return temp_cwd(self)

    def __str__(self):
        return self._location

    def __repr__(self):
        if self._connection == self.get_default_connection():
            return type(self).__name__ + '(' + repr(str(self)) + ')'
        else:
            return type(self).__name__ + repr((str(self), self._connection))

    def __abs__(self):
        return self._connection.abs_path(self)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, Path):
            return NotImplemented
        return str(self) == str(other) and self._connection == other._connection

    def __ne__(self, other):
        if not isinstance(other, Path):
            return NotImplemented
        return str(self) != str(other) or self._connection != other._connection

    def __lt__(self, other):
        if not isinstance(other, Path):
            return NotImplemented

        self_str = str(self)

        if len(self_str) >= len(str(other)):
            return False

        current = other.dir
        while current is not None:
            current_str = str(current)
            if len(self_str) > len(current_str):
                return False
            if self_str == current_str:
                return True
            current = current.dir

        return False

    def __le__(self, other):
        if not isinstance(other, Path):
            return NotImplemented

        self_str = str(self)

        current = other
        while current is not None:
            current_str = str(current)
            if len(self_str) > len(current_str):
                return False
            if self_str == current_str:
                return True
            current = current.dir

        return False

    def __gt__(self, other):
        if not isinstance(other, Path):
            return NotImplemented

        other_str = str(other)

        if len(str(self)) <= len(other_str):
            return False

        current = self.dir
        while current is not None:
            current_str = str(current)
            if len(current_str) < len(other_str):
                return False
            if current_str == other_str:
                return True
            current = current.dir

        return False

    def __ge__(self, other):
        if not isinstance(other, Path):
            return NotImplemented

        other_str = str(other)

        current = self
        while current is not None:
            current_str = str(current)
            if len(current_str) < len(other_str):
                return False
            if current_str == other_str:
                return True
            current = current.dir

        return False

    def __iter__(self):
        if self.is_dir:
            return iter(self.glob())
        else:
            return iter([])

    def __contains__(self, item):
        if isinstance(item, str):
            assert item
            return item in self.list() or Path(item, self._connection) in self.glob()
        else:
            assert isinstance(item, Path)
            return item in self.glob()

    def __len__(self):
        return len(self.list())

    def __getitem__(self, item):
        assert isinstance(item, (str, Path))
        return self._connection.join(self, item)

    def __and__(self, other):
        if not isinstance(other, Path) or self._connection != other.connection:
            return NotImplemented
        this = self
        while str(this) != str(other):
            if len(str(this)) > len(str(other)):
                this = this.dir
            elif len(str(this)) < len(str(other)):
                other = other.dir
            else:
                this = this.dir
                other = other.dir
            if this is None or other is None:
                return None
        return this

    @property
    def is_dir(self):
        """Whether this path refers to an existing directory."""
        return self._connection.is_dir(self)

    @property
    def is_file(self):
        """Whether this path refers to an existing file."""
        return self._connection.is_file(self)

    @property
    def exists(self):
        """Whether this path refers to an existing file system object."""
        return self._connection.exists(self)

    @property
    def protection_mode(self):
        """The protection mode bits of the file system object."""
        return self._connection.protection_mode(self)

    @property
    def inode_number(self):
        """The inode number of the file system object."""
        return self._connection.inode_number(self)

    @property
    def device(self):
        """The device of the file system object."""
        return self._connection.device(self)

    @property
    def hard_link_count(self):
        """The number of hard links to the file system object."""
        return self._connection.hard_link_count(self)

    @property
    def owner_user_id(self):
        """The user ID of the owner of the file system object."""
        return self._connection.owner_user_id(self)

    @property
    def owner_group_id(self):
        """The group ID of the owner of the file system object."""
        return self._connection.owner_group_id(self)

    @property
    def size(self):
        """The size of the file system object."""
        return self._connection.size(self)

    @property
    def accessed_time(self):
        """The last time the file system object was accessed."""
        return self._connection.accessed_time(self)

    @property
    def modified_time(self):
        """The last time the data of file system object was modified."""
        return self._connection.modified_time(self)

    @property
    def metadata_changed_time(self):
        """The last time the data or metadata of the file system object was modified."""
        return self._connection.metadata_changed_time(self)

    @property
    def name(self):
        """The name of the file system object."""
        return self._connection.name(self)

    @property
    def dir(self):
        """The parent directory of the file system object."""
        return self._connection.dir(self)

    @property
    def bare_name(self):
        """The name of the file system object, minus any extension."""
        return self._connection.bare_name(self)

    @property
    def extension(self):
        """The extension of the file system object, or the empty string."""
        return self._connection.extension(self)

    def find(self, include_cwd=True):
        """
        Try to look up the file system object using the PATH system environment variable. Return the
        located file system object (as a Path instance) on success or None on failure. (To modify
        the PATH in Windows, go to Start -> Settings -> Control Panel -> System -> Advanced ->
        Environment Variables, then select PATH in the "System variables" list, and click Edit.)

        :param include_cwd: Whether the current working directory be checked before the PATH.
        :return: A Path representing the located object, or None.
        """
        return self._connection.find(self, include_cwd)

    def list(self, pattern='*'):
        """
        Return a list of the names of the files and directories appearing in this folder.

        :param pattern: A glob-style pattern against which names must match.
        :return: A list of matching file and directory names.
        """
        return self._connection.list(self, pattern)

    def glob(self, pattern='*'):
        """
        Return a list of the paths to the files and directories appearing in this folder.

        :param pattern: A glob-style pattern against which names must match.
        :return: A list of Path instances for each matching file and directory name.
        """
        return self._connection.glob(self, pattern)

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True,
             opener=None):
        """
        Open the file.

        :param mode: The file mode.
        :param buffering: The buffering policy.
        :param encoding: The encoding.
        :param errors: The error handling strategy.
        :param newline: The character sequence to use for newlines.
        :param closefd: Whether to close the descriptor after the file closes.
        :param opener: A custom opener.
        :return: The opened file object.
        """
        return self._connection.open_file(
            self,
            mode,
            buffering,
            encoding,
            errors,
            newline,
            closefd,
            opener
        )

    def read(self, encoding=None):
        """
        Return an iterator over the lines from the file.

        :param encoding: The file encoding used to open the file.
        :return: An iterator over the lines in the file, without newlines.
        """
        return self._connection.read(self, encoding)

    def load(self, encoding=None):
        """
        Returns a list containing the lines from the file.

        :param encoding: The file encoding used to open the file.
        :return: A list containing the lines in the file, without newlines.
        """
        return self._connection.load(self, encoding)

    def read_delimited(self, delimiter=',', quote='"', encoding=None):
        """
        Return an iterator over the records from the file.

        :param delimiter: The delimiter used to separate fields in each record.
        :param quote: The quote character used to surround field values in the record.
        :param encoding: The file encoding used to open the file.
        :return: An iterator over the rows in the file.
        """
        return self._connection.read_delimited(self, delimiter, quote, encoding)

    def load_delimited(self, delimiter=',', quote='"', encoding=None):
        """
        Return a list of the records from the file.

        :param delimiter: The delimiter used to separate fields in each record.
        :param quote: The quote character used to surround field values in the record.
        :param encoding: The file encoding used to open the file.
        :return: A list containing the rows in the file.
        """
        return self._connection.load_delimited(self, delimiter, quote, encoding)

    def save(self, lines, overwrite=False, append=False, encoding=None):
        """
        Save a sequence of lines to a file.

        :param lines: An iterator or iterable container over the lines to be written.
        :param overwrite: Whether to overwrite the file if it already exists.
        :param append: Whether to append to the file if it already exists.
        :param encoding: The encoding of the file.
        :return: The number of lines written.
        """
        return self._connection.save(self, lines, overwrite, append, encoding)

    def save_delimited(self, rows, delimiter=',', quote='"', overwrite=False, append=False,
                       encoding=None):
        """
        Save a sequence of rows to a file.

        :param rows: An iterator or iterable container over the rows to be written.
        :param delimiter: The delimiter used to separate fields in a given row.
        :param quote: The quote character used to surround field values.
        :param overwrite: Whether to overwrite the file if it already exists.
        :param append: Whether to append to the file if it already exists.
        :param encoding: The encoding of the file.
        :return: The number of lines written.
        """
        return self._connection.save_delimited(
            self,
            rows,
            delimiter,
            quote,
            overwrite,
            append,
            encoding
        )

    def is_available(self, mode='r'):
        """
        Check to see if the file is available to read or write.

        :param mode: The desired access to the file, either 'r' (default) or 'w'.
        """
        return self._connection.is_available(self, mode)

    def is_stable(self, interval=None):
        """
        Watches for file size changes over time.  Returns a Boolean indicating whether the file's
        size was constant over the given interval.

        :param interval: The number of seconds to wait between checks. Default is 1 second.
        """
        return self._connection.is_stable(self, interval)

    def remove(self):
        """
        Remove the folder or file.
        """
        return self._connection.remove(self)

    def discard(self):
        """
        Remove the folder or file.
        """
        return self._connection.discard(self)

    def make_dir(self, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Create a directory at this location.

        :param overwrite: Whether existing files/folders that conflict with this function are to be
            deleted/overwritten.
        :param clear: Whether the directory at this location must be empty for the function to be
            satisfied.
        :param fill: Whether the necessary parent folder(s) are to be created if the do not exist
            already.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """
        return self._connection.make_dir(self, overwrite, clear, fill, check_only)

    def copy_into(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Recursively copy the folder or file to the destination. The file or folder is added to the
        destination folder's listing and is not renamed in the process.

        :param destination: The location of the containing folder where this file system object will
            be copied.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the destination folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """
        return self._connection.copy_into(self, destination, overwrite, clear, fill, check_only)

    def copy_to(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Recursively copy the folder or file to the destination. The file or folder is renamed to the
        destination's name in the process if the names differ.

        :param destination: The new location where this file system object will be copied.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the parent folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """
        return self._connection.copy_to(self, destination, overwrite, clear, fill, check_only)

    def move_into(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Move the folder or file to the destination. The file or folder is added to the destination
        folder's listing and is not renamed in the process.

        :param destination: The location of the containing folder where this file system object will
            be moved.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the destination folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """
        return self._connection.move_into(self, destination, overwrite, clear, fill, check_only)

    def move_to(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Move the folder or file to the destination. The file or folder is renamed to the
        destination's name in the process if the names differ.

        :param destination: The new location where this file system object will be moved.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the parent folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """
        return self._connection.move_to(self, destination, overwrite, clear, fill, check_only)

    def find_unique_file(self, pattern='*', most_recent=True):
        """
        Find a file in the folder matching the given pattern and return it. If no such file is
        found, return None. If multiple files are found, either disambiguate by recency if
        most_recent is set, or raise an exception if most_recent is not set.

        :param pattern: The pattern which the file must match. Default is '*" (all files).
        :param most_recent: Whether to use recency to disambiguate when multiple files are matched
            by the pattern.
        :return: The uniquely identified file, as a Path instance, or None.
        """
        return self._connection.find_unique_file(self, pattern, most_recent)


class FSConnector(Connector, Configurable, metaclass=ABCMeta):
    """
    The FSConnector class is an abstract base class for file system connectors.
    """

    @classmethod
    @abstractmethod
    def load_url(cls, config_loader, url):
        """
        Load a new Path instance from a URL string.

        :param config_loader: The ConfigLoader instance.
        :param url: The URL to load.
        :return: The resultant Path instance.
        """
        raise NotImplementedError()

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        verify_type(config_loader, configurations.ConfigLoader)
        verify_type(value, str)
        assert cls is not FSConnector  # Must be a subclass
        return cls(*args, initial_cwd=value, **kwargs)

    @classmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(config_loader, configurations.ConfigLoader)
        verify_type(section, str, non_empty=True)
        assert cls is not FSConnector  # Must be a subclass

        initial_cwd = config_loader.load_option(section, 'Initial CWD', str, None)

        return cls(*args, initial_cwd=initial_cwd, **kwargs)

    def __init__(self, connection_type, initial_cwd=None):
        verify_type(connection_type, type)
        assert issubclass(connection_type, fs_connection)
        if initial_cwd is not None:
            verify_type(initial_cwd, str)
        super().__init__(connection_type)
        self._initial_cwd = initial_cwd

    @property
    def initial_cwd(self):
        """The initial CWD for new connections."""
        return self._initial_cwd

    @initial_cwd.setter
    def initial_cwd(self, cwd):
        """The initial CWD for new connections."""
        if cwd is not None:
            verify_type(cwd, str)
        self._initial_cwd = cwd or None

    def connect(self, *args, **kwargs):
        """Create a new connection and return it."""
        result = super().connect(*args, **kwargs)
        if self._initial_cwd is not None:
            result.cwd = self._initial_cwd
        return result


# noinspection PyPep8Naming
class fs_connection(connection, Configurable, metaclass=ABCMeta):
    """
    The fs_connection class is an abstract base class for connections to file systems, e.g.
    local_fs_connection, http_fs_connection, ftp_fs_connection, etc. Classes which inherit from this
    class are responsible for handling file-system interactions on behalf of Path instances that use
    them as their respective connection objects.
    """

    @classmethod
    @abstractmethod
    def get_connector_type(cls):
        """Get the connector type associated with this connection type."""
        raise NotImplementedError()

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        verify_type(config_loader, configurations.ConfigLoader)
        assert isinstance(config_loader, configurations.ConfigLoader)
        verify_type(value, str)
        connector = config_loader.load_value(value, cls.get_connector_type())
        return cls(*args, connector=connector, **kwargs)

    @classmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param config_loader: An attila.configurations.ConfigLoader instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(config_loader, configurations.ConfigLoader)
        assert isinstance(config_loader, configurations.ConfigLoader)
        verify_type(section, str, non_empty=True)

        if config_loader.has_option(section, 'Connector'):
            connector = config_loader.load_option(section, 'Connector', cls.get_connector_type())
        else:
            connector = config_loader.load_section(section, cls.get_connector_type())
        return cls(*args, connector=connector, **kwargs)

    def __init__(self, connector):
        assert isinstance(connector, FSConnector)
        super().__init__(connector)

    def __eq__(self, other):
        if not isinstance(other, fs_connection):
            return NotImplemented
        return self is other

    def __ne__(self, other):
        if not isinstance(other, fs_connection):
            return NotImplemented
        return not (self == other)

    @property
    def cwd(self):
        """
        The current working directory of this file system connection, or None if CWD functionality
        is not supported.
        """
        return None

    @cwd.setter
    def cwd(self, path):
        """
        The current working directory of this file system connection, or None if CWD functionality
        is not supported.
        """
        raise OperationNotSupportedError()

    def check_path(self, path):
        """
        Verify that the path is valid for this file system connection, and return it in string form.

        :param path: The path to check.
        :return: The path, as a string value.
        """
        if isinstance(path, str):
            return path
        else:
            assert isinstance(path, Path)
            assert path.connection == self
            return str(path)

    def find(self, path, include_cwd=True):
        """
        Try to look up the file system object using the PATH system environment variable. Return the
        located file system object (as a Path instance) on success or None on failure. (To modify
        the PATH in Windows, go to Start -> Settings -> Control Panel -> System -> Advanced ->
        Environment Variables, then select PATH in the "System variables" list, and click Edit.)

        :param path: The path to operate on.
        :param include_cwd: Whether the current working directory be checked before the PATH.
        :return: A Path representing the located object, or None.
        """

        raise OperationNotSupportedError()

    @property
    def temp_dir(self):
        """
        Locate a directory that can be safely used for temporary files.

        :return: The path to the temporary directory, or None.
        """
        return None

    def get_temp_file_path(self, name_base=None):
        """
        Locate a path where a temporary file can be safely created.

        :param name_base: An optional base for the file name.
        :return: A temporary file path, or None.
        """
        if name_base is None:
            name_base = 'temp'
        temp_dir = self.temp_dir
        if temp_dir is None:
            return None
        while True:
            path = self.temp_dir[name_base + '_' + time.strftime('%Y%m%d%H%M%S')]
            if not path.exists:
                return path

    def abs_path(self, path):
        """
        Return an absolute form of a potentially relative path.

        :param path: The path to operate on.
        :return: The absolute path.
        """
        return Path(self.check_path(path), self)

    def join(self, *path_elements):
        """
        Join several path elements together into a single path.

        :param path_elements: The path elements to join.
        :return: The resulting path.
        """
        if path_elements:
            return Path(os.path.join(*(self.check_path(element) for element in path_elements)),
                        self)
        else:
            return Path(connection=self)

    def is_dir(self, path):
        """
        Determine if the path refers to an existing directory.

        :param path: The path to operate on.
        :return: Whether the path is a directory.
        """
        raise OperationNotSupportedError()

    def is_file(self, path):
        """
        Determine if the path refers to an existing file.

        :param path: The path to operate on.
        :return: Whether the path is a file.
        """
        raise OperationNotSupportedError()

    def exists(self, path):
        """
        Determine if the path refers to an existing file object.

        :param path: The path to operate on.
        :return: Whether the path exists.
        """
        return self.is_dir(path) or self.is_file(path)

    def protection_mode(self, path):
        """
        Return the protection mode of the path.

        :param path: The path to operate on.
        :return: The protection mode bits.
        """
        raise OperationNotSupportedError()

    def inode_number(self, path):
        """
        Get the inode number of the file system object.

        :param path: The path to operate on.
        :return: The inode number.
        """
        raise OperationNotSupportedError()

    def device(self, path):
        """
        Get the device of the file system object.

        :param path: The path to operate on.
        :return: The device.
        """
        raise OperationNotSupportedError()

    def hard_link_count(self, path):
        """
        Get the number of hard links to the file system object.

        :param path: The path to operate on.
        :return: The number of hard links.
        """
        raise OperationNotSupportedError()

    def owner_user_id(self, path):
        """
        Get the user ID of the owner of the file system object.

        :param path: The path to operate on.
        :return: The owner's user ID.
        """
        raise OperationNotSupportedError()

    def owner_group_id(self, path):
        """
        The group ID of the owner of the file system object.

        :param path: The path to operate on.
        :return: The owner's group ID.
        """
        raise OperationNotSupportedError()

    def size(self, path):
        """
        Get the size of the file.

        :param path: The path to operate on.
        :return: The size in bytes.
        """
        raise OperationNotSupportedError()

    def accessed_time(self, path):
        """
        Get the last time the file system object was accessed.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        return self.modified_time(path)

    def modified_time(self, path):
        """
        Get the last time the data of file system object was modified.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        raise OperationNotSupportedError()

    def metadata_changed_time(self, path):
        """
        Get the last time the data or metadata of the file system object was modified.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        return self.modified_time(path)

    def name(self, path):
        """
        Get the name of the file system object.

        :param path: The path to operate on.
        :return: The name.
        """
        return os.path.basename(self.check_path(path))

    def dir(self, path):
        """
        Get the parent directory of the file system object.

        :param path: The path to operate on.
        :return: The parent directory's path, or None.
        """
        path = self.check_path(path)
        dir_path = os.path.dirname(path)
        if dir_path == path:
            return None
        else:
            return Path(dir_path, self)

    def bare_name(self, path):
        """
        Get the name of the file system object, minus any extension.

        :param path: The path to operate on.
        :return: The name, minus any extension.
        """
        return os.path.splitext(os.path.basename(self.check_path(path)))[0]

    def extension(self, path):
        """
        Get the extension of the file system object, or the empty string.

        :param path: The path to operate on.
        :return: The extension.
        """
        return os.path.splitext(self.check_path(path))[-1]

    def list(self, path, pattern='*'):
        """
        Return a list of the names of the files and directories appearing in this folder.

        :param path: The path to operate on.
        :param pattern: A glob-style pattern against which names must match.
        :return: A list of matching file and directory names.
        """
        raise OperationNotSupportedError()

    def glob(self, path, pattern='*'):
        """
        Return a list of the paths to the files and directories appearing in this folder.

        :param path: The path to operate on.
        :param pattern: A glob-style pattern against which names must match.
        :return: A list of Path instances for each matching file and directory name.
        """
        path = self.check_path(path)
        return [self.join(path, child) for child in self.list(path, pattern)]

    def open_file(self, path, mode='r', buffering=-1, encoding=None, errors=None, newline=None,
                  closefd=True, opener=None):
        """
        Open the file.

        :param path: The path to operate on.
        :param mode: The file mode.
        :param buffering: The buffering policy.
        :param encoding: The encoding.
        :param errors: The error handling strategy.
        :param newline: The character sequence to use for newlines.
        :param closefd: Whether to close the descriptor after the file closes.
        :param opener: A custom opener.
        :return: The opened file object.
        """
        raise OperationNotSupportedError()

    def read(self, path, encoding=None):
        """
        Return an iterator over the lines from the file.

        :param path: The path to operate on.
        :param encoding: The file encoding used to open the file.
        :return: An iterator over the lines in the file, without newlines.
        """
        assert self.is_file(path)

        with self.open_file(path, encoding=encoding) as file_obj:
            for line in file_obj:
                line = line.rstrip('\r\n')
                for piece in line.split(FORM_FEED_CHAR):
                    yield piece

    def load(self, path, encoding=None):
        """
        Returns a list containing the lines from the file.

        :param path: The path to operate on.
        :param encoding: The file encoding used to open the file.
        :return: A list containing the lines in the file, without newlines.
        """
        return list(self.read(path, encoding))

    def read_delimited(self, path, delimiter=',', quote='"', encoding=None):
        """
        Return an iterator over the records from the file.

        :param path: The path to operate on.
        :param delimiter: The delimiter used to separate fields in each record.
        :param quote: The quote character used to surround field values in the record.
        :param encoding: The file encoding used to open the file.
        :return: An iterator over the rows in the file.
        """
        with self.open_file(path, encoding=encoding, newline='') as file_obj:
            reader = csv.reader(file_obj, delimiter=delimiter, quotechar=quote)

            # This is necessary because the reader only keeps a weak reference to the file, which
            # means we can't just return the reader.
            for row in reader:
                yield row

    def load_delimited(self, path, delimiter=',', quote='"', encoding=None):
        """
        Return a list of the records from the file.

        :param path: The path to operate on.
        :param delimiter: The delimiter used to separate fields in each record.
        :param quote: The quote character used to surround field values in the record.
        :param encoding: The file encoding used to open the file.
        :return: A list containing the rows in the file.
        """
        return list(self.read_delimited(path, delimiter, quote, encoding))

    def save(self, path, lines, overwrite=False, append=False, encoding=None):
        """
        Save a sequence of lines to a file.

        :param path: The path to operate on.
        :param lines: An iterator or iterable container over the lines to be written.
        :param overwrite: Whether to overwrite the file if it already exists.
        :param append: Whether to append to the file if it already exists.
        :param encoding: The encoding of the file.
        :return: The number of lines written.
        """
        path = self.check_path(path)
        assert not overwrite or not append
        assert not self.exists(path) or ((overwrite or append) and self.is_file(path))

        with self.open_file(path, mode=('a' if append else 'w'), encoding=encoding) as file_obj:
            index = -1
            for index, line in enumerate(lines):
                file_obj.write(line.rstrip('\r\n') + '\n')
            return index + 1

    def save_delimited(self, path, rows, delimiter=',', quote='"', overwrite=False, append=False,
                       encoding=None):
        """
        Save a sequence of rows to a file.

        :param path: The path to operate on.
        :param rows: An iterator or iterable container over the rows to be written.
        :param delimiter: The delimiter used to separate fields in a given row.
        :param quote: The quote character used to surround field values.
        :param overwrite: Whether to overwrite the file if it already exists.
        :param append: Whether to append to the file if it already exists.
        :param encoding: The encoding of the file.
        :return: The number of lines written.
        """
        path = self.check_path(path)
        assert not overwrite or not append
        assert not self.exists(path) or ((overwrite or append) and self.is_file(path))

        with self.open_file(path, mode=('a' if append else 'w'), encoding=encoding, newline='') \
                as file_obj:
            writer = csv.writer(file_obj, delimiter=delimiter, quotechar=quote)
            index = -1
            for index, row in enumerate(rows):
                writer.writerow(row)
            return index + 1

    def is_available(self, path, mode='r'):
        """
        Check to see if the file is available to read or write.

        :param path: The path to operate on.
        :param mode: The desired access to the file, either 'r' (default) or 'w'.
        """

        path = self.check_path(path)

        assert mode in ('r', 'w')

        if not self.exists(path):
            return mode == 'w'

        assert not self.is_dir(path)

        if mode == 'w':
            open_mode = 'a'
        else:
            open_mode = 'r'

        # Try to open the file, then immediately close it again. This will error if the file cannot
        # be accessed, but it won't change the contents of the file in any case.
        # noinspection PyBroadException
        try:
            with self.open_file(path, mode=open_mode):
                return True
        except Exception:
            return False

    def is_stable(self, path, interval=None):
        """
        Watches for file size changes over time.  Returns a Boolean indicating whether the file's
        size was constant over the given interval.

        :param path: The path to operate on.
        :param interval: The number of seconds to wait between checks. Default is 1 second.
        """

        assert interval is None or interval > 0
        if interval is None:
            interval = 1

        initial_size = self.size(path)
        time.sleep(interval)
        return initial_size == self.size(path)

    def remove(self, path):
        """
        Remove the folder or file.

        :param path: The path to operate on.
        """
        raise OperationNotSupportedError()

    def discard(self, path):
        """
        Remove the folder or file.

        :param path: The path to operate on.
        """

        if self.exists(path):
            self.remove(path)

    def make_dir(self, path, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Create a directory at this location.

        :param path: The path to operate on.
        :param overwrite: Whether existing files/folders that conflict with this function are to be
            deleted/overwritten.
        :param clear: Whether the directory at this location must be empty for the function to be
            satisfied.
        :param fill: Whether the necessary parent folder(s) are to be created if the do not exist
            already.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """

        raise OperationNotSupportedError()

    def raw_copy(self, path, destination):
        """
        Copy from a specific path to another specific path, with no validation.

        :param path: The path to operate on.
        :param destination: The path to copy to.
        :return: None
        """
        path = self.check_path(path)
        verify_type(destination, Path)
        with self.open_file(path, mode='rb') as source_file:
            with destination.connection.open_file(destination, mode='wb') as target_file:
                for line in source_file:
                    target_file.write(line)

    def copy_into(self, path, destination, overwrite=False, clear=False, fill=True,
                  check_only=None):
        """
        Recursively copy the folder or file to the destination. The file or folder is added to the
        destination folder's listing and is not renamed in the process.

        :param path: The path to operate on.
        :param destination: The location of the containing folder where this file system object will
            be copied.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the destination folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """

        self.copy_to(path, destination[self.name], overwrite, clear, fill, check_only)

    def copy_to(self, path, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Recursively copy the folder or file to the destination. The file or folder is renamed to the
        destination's name in the process if the names differ.

        :param path: The path to operate on.
        :param destination: The new location where this file system object will be copied.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the parent folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """

        if check_only is None:
            # First check to see if it can be done before we actually make any changes. This doesn't
            # make the whole thing perfectly atomic, but it eliminates most cases where we start to
            # do things and then find out we shouldn't have.

            self.copy_to(self, destination, overwrite, clear, fill, check_only=True)

            # If we don't do this, we'll do a redundant check first on each step in the recursion.
            check_only = False

        path = self.check_path(path)

        assert isinstance(destination, Path)
        assert self.exists(path)

        # Create the target directory, if necessary. Do not clear it, regardless of the clear flag's
        # value, as this is the new *parent* folder of the file object to be copied, and the clear
        # flag only applies to the copied file object and its descendants.
        destination.dir.make_dir(overwrite, clear=False, fill=fill, check_only=check_only)

        if self.is_dir(path):
            destination.make_dir(overwrite, clear, fill, check_only)
            for child in self.glob(path):
                child.copy_into(destination, overwrite, clear, fill, check_only)
        else:
            assert self.is_file(path)

            if destination.exists:
                # It's not a folder, and it's in our way.
                if not overwrite:
                    if destination.is_dir:
                        raise IsADirectoryError(destination)
                    else:
                        raise FileExistsError(destination)
                if not check_only:
                    destination.remove()
            if not check_only:
                self.raw_copy(path, destination)

    def move_into(self, path, destination, overwrite=False, clear=False, fill=True,
                  check_only=None):
        """
        Move the folder or file to the destination. The file or folder is added to the destination
        folder's listing and is not renamed in the process.

        :param path: The path to operate on.
        :param destination: The location of the containing folder where this file system object will
            be moved.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the destination folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """

        self.move_to(path, destination[self.name], overwrite, clear, fill, check_only)

    def move_to(self, path, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Move the folder or file to the destination. The file or folder is renamed to the
        destination's name in the process if the names differ.

        :param path: The path to operate on.
        :param destination: The new location where this file system object will be moved.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the parent folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually
            perform the operation.
        :return: None
        """

        self.copy_to(path, destination, overwrite, clear, fill, check_only)
        self.remove(path)

    def rename(self, path, new_name):
        """
        Rename a file object.

        :param path: The path to be operated on.
        :param new_name: The new name of the file object, as as string.
        :return: None
        """
        path = Path(self.check_path(path), self)
        assert new_name and isinstance(new_name, str)
        if path.name != new_name:
            self.move_to(path, path.dir[new_name], overwrite=False, clear=True, fill=False)

    def find_unique_file(self, path, pattern='*', most_recent=True):
        """
        Find a file in the folder matching the given pattern and return it. If no such file is
        found, return None. If multiple files are found, either disambiguate by recency if
        most_recent is set, or raise an exception if most_recent is not set.

        :param path: The path to operate on.
        :param pattern: The pattern which the file must match. Default is '*" (all files).
        :param most_recent: Whether to use recency to disambiguate when multiple files are matched
            by the pattern.
        :return: The uniquely identified file, as a Path instance, or None.
        """

        path = self.check_path(path)

        if not self.is_dir(path):
            raise NotADirectoryError(path)

        # Get a list of files matching the pattern. Ignore Microsoft Office temporary files, which
        # start with '~$'.
        files = [path for path in self.glob(path, pattern) if not path.name.startswith('~$')]

        # If nothing was found, return None
        if not files:
            log.info("No file found matching the pattern %s in the folder %s.", pattern, path)
            return None

        # Log the files we found
        if log.level <= logging.INFO:
            log.info("Source file(s) identified:")
            for file_path in files:
                log.info("    %s", str(file_path))

        # If only one file was found, return it. Otherwise, either blow up or use
        # the most recent, depending on parameter settings.
        if len(files) == 1:
            return files[0]
        elif most_recent:
            log.info("Only the most recent file will be used.")
            result = max(files, key=lambda matched_path: matched_path.modified_time)
            log.info("Most recent file: %s", result)
            return result
        else:
            raise FileExistsError(
                "Multiple files identified matching the pattern %s in folder %s." % (pattern, path)
            )
