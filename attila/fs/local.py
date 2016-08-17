"""
Local file system support
"""

import glob
import os
import shutil
import stat
import tempfile

from urllib.parse import urlparse

from ..abc.files import Path, FSConnector, fs_connection
from ..configurations import ConfigManager
from ..exceptions import DirectoryNotEmptyError, verify_type
from ..plugins import config_loader, url_scheme


__author__ = 'Aaron Hosford'
__all__ = [
    'LocalFSConnector',
    'local_fs_connection',
]


@config_loader
@url_scheme('file')
class LocalFSConnector(FSConnector):
    """
    Stores the local files system connection information.
    """

    @classmethod
    def load_url(cls, manager, url):
        """
        Load a new Path instance from a URL string.

        The standard format for a local URL is "file://path".

        :param manager: The ConfigManager instance.
        :param url: The URL to load.
        :return: The resultant Path instance.
        """
        verify_type(manager, ConfigManager)
        verify_type(url, str)

        if '://' not in url:
            url = 'file://' + url
        scheme, netloc, path, params, query, fragment = urlparse(url)
        assert not params and not query and not fragment
        assert scheme.lower() == 'file'
        assert '@' not in netloc

        return Path(url[7:], cls().connect())

    def __init__(self, initial_cwd=None):
        super().__init__(local_fs_connection, initial_cwd)

    def connect(self):
        """Create a new connection and return it."""
        return super().connect()


# noinspection PyPep8Naming
@config_loader
class local_fs_connection(fs_connection):
    """
    local_fs_connection implements an interface for the local file system, handling interactions
    with it on behalf of Path instances.
    """

    @classmethod
    def get_connector_type(cls):
        """Get the connector type associated with this connection type."""
        return LocalFSConnector

    def __init__(self, connector=None):
        if connector is None:
            connector = LocalFSConnector()
        else:
            verify_type(connector, LocalFSConnector)
        super().__init__(connector)
        super().open()  # local fs connections are always open.

    def open(self):
        """Open the connection."""
        pass  # local fs connections are always open.

    def close(self):
        """Close the connection"""
        pass  # local fs connections are always open.

    def __repr__(self):
        return type(self).__name__ + '()'

    def __eq__(self, other):
        if not isinstance(other, fs_connection):
            return NotImplemented
        return isinstance(other, local_fs_connection)

    def is_local(self, path):
        """
        Whether the path refers to a local file system object.

        :param path: The path to check.
        :return: A bool.
        """
        self.check_path(path)
        return True

    @property
    def cwd(self):
        """The current working directory of this file system connection."""
        # TODO: Should we track the CWD separately for each instance? The OS itself only provides
        #       one CWD per process, but for other new_instance types (e.g. FTP) the CWD is a
        #       per-new_instance value, and this might lead to slight incompatibilities between the
        #       different new_instance types which could destroy the abstraction I've built.
        return Path(os.getcwd(), self)

    @cwd.setter
    def cwd(self, path):
        """The current working directory of this file system connection."""
        os.chdir(self.check_path(path))

    def check_path(self, path, expand_user=True, expand_vars=True):
        """
        Verify that the path is valid for this file system connection, and return it in string form.

        :param path: The path to check.
        :param expand_user: Whether to expand the user home symbol (~).
        :param expand_vars: Whether to expand environment variables appearing in the path.
        :return: The path, as a string value.
        """
        path = super().check_path(path)
        if expand_user:
            path = os.path.expanduser(path)
        if expand_vars:
            path = os.path.expandvars(path)
        return path

    def find(self, path, include_cwd=True):
        """
        Try to look up the file system object using the PATH system environment variable. Return the
        located file system object (as a Path instance) on success or None on failure. (To modify
        the PATH, go to Start -> Settings -> Control Panel -> System -> Advanced ->
        Environment Variables, then select PATH in the "System variables" list, and click Edit.)

        :param path: The path to operate on.
        :param include_cwd: Whether the current working directory be checked before the PATH.
        :return: A Path representing the located object, or None.
        """

        path = self.check_path(path)

        if include_cwd and self.exists(path):
            return Path(path, self)

        if 'PATH' in os.environ:
            for base in os.environ['PATH'].split(';'):
                path = Path(base, self)[path]
                if path.exists:
                    return path

        return None

    def temp_dir(self):
        """
        Locate a directory that can be safely used for temporary files.

        :return: The path to the temporary directory, or None.
        """
        return Path(tempfile.gettempdir(), self)

    def abs_path(self, path):
        """
        Return an absolute form of a potentially relative path.

        :param path: The path to operate on.
        :return: The absolute path.
        """
        return Path(os.path.abspath(self.check_path(path)), self)

    def is_dir(self, path):
        """
        Determine if the path refers to an existing directory.

        :param path: The path to operate on.
        :return: Whether the path is a directory.
        """
        return os.path.isdir(self.check_path(path))

    def is_file(self, path):
        """
        Determine if the path refers to an existing file.

        :param path: The path to operate on.
        :return: Whether the path is a file.
        """
        return os.path.isfile(self.check_path(path))

    def exists(self, path):
        """
        Determine if the path refers to an existing file object.

        :param path: The path to operate on.
        :return: Whether the path exists.
        """
        return os.path.exists(self.check_path(path))

    def protection_mode(self, path):
        """
        Return the protection mode of the path.

        :param path: The path to operate on.
        :return: The protection mode bits.
        """
        return os.stat(self.check_path(path)).st_mode

    def inode_number(self, path):
        """
        Get the inode number of the file system object.

        :param path: The path to operate on.
        :return: The inode number.
        """
        return os.stat(self.check_path(path)).st_ino

    def device(self, path):
        """
        Get the device of the file system object.

        :param path: The path to operate on.
        :return: The device.
        """
        return os.stat(self.check_path(path)).st_dev

    def hard_link_count(self, path):
        """
        Get the number of hard links to the file system object.

        :param path: The path to operate on.
        :return: The number of hard links.
        """
        return os.stat(self.check_path(path)).st_nlink

    def owner_user_id(self, path):
        """
        Get the user ID of the owner of the file system object.

        :param path: The path to operate on.
        :return: The owner's user ID.
        """
        return os.stat(self.check_path(path)).st_uid

    def owner_group_id(self, path):
        """
        The group ID of the owner of the file system object.

        :param path: The path to operate on.
        :return: The owner's group ID.
        """
        return os.stat(self.check_path(path)).st_gid

    def size(self, path):
        """
        Get the size of the file.

        :param path: The path to operate on.
        :return: The size in bytes.
        """
        return os.stat(self.check_path(path)).st_size

    def accessed_time(self, path):
        """
        Get the last time the file system object was accessed.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        return os.stat(self.check_path(path)).st_atime

    def modified_time(self, path):
        """
        Get the last time the data of file system object was modified.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        return os.stat(self.check_path(path)).st_mtime

    def metadata_changed_time(self, path):
        """
        Get the last time the data or metadata of the file system object was modified.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        return os.stat(self.check_path(path)).st_ctime

    def list(self, path, pattern='*'):
        """
        Return a list of the names of the files and directories appearing in this folder.

        :param path: The path to operate on.
        :param pattern: A glob-style pattern against which names must match.
        :return: A list of matching file and directory names.
        """
        path = self.check_path(path)
        self.verify_is_dir(path)

        if pattern == '*':
            return os.listdir(path)

        return [Path(match, self).name for match in glob.iglob(os.path.join(path, pattern))]

    def glob(self, path, pattern='*'):
        """
        Return a list of the source_paths to the files and directories appearing in this folder.

        :param path: The path to operate on.
        :param pattern: A glob-style pattern against which names must match.
        :return: A list of Path instances for each matching file and directory name.
        """
        path = self.check_path(path)
        self.verify_is_dir(path)
        return [Path(match, self) for match in glob.iglob(os.path.join(path, pattern))]

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
        path = self.check_path(path)

        verify_type(mode, str, non_empty=True)
        mode = mode.lower()

        self.verify_is_not_dir(path)

        return open(path, mode, buffering, encoding, errors, newline, closefd, opener)

    def remove(self, path):
        """
        Remove the folder or file.

        :param path: The path to operate on.
        """
        path = self.check_path(path)

        self.verify_exists(path)

        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWRITE)

        if self.is_dir(path):
            for child in self.glob(path):
                child.remove()
            os.rmdir(path)
        else:
            os.remove(path)

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
        path = self.check_path(path)

        if check_only is None:
            # First check to see if it can be done before we actually make any changes. This doesn't
            # make the whole thing perfectly atomic, but it eliminates most cases where we start to
            # do things and then find out we shouldn't have.
            self.make_dir(path, overwrite, clear, fill, check_only=True)

            # If we don't do this, we'll do a redundant check first on each step in the recursion.
            check_only = False

        if self.is_dir(path):
            if clear:
                children = self.glob(path)
                if children:
                    if not overwrite:
                        raise DirectoryNotEmptyError(path)
                    if not check_only:
                        for child in children:
                            child.remove()
        elif self.exists(path):
            # It's not a folder, and it's in our way.
            if not overwrite:
                raise FileExistsError(path)
            if not check_only:
                self.remove(path)
                os.mkdir(path)
        else:
            # The path doesn't exist yet, so we need to create it.

            # First ensure the parent folder exists.
            if not self.dir(path).is_dir:
                if not fill:
                    raise NotADirectoryError(self.dir(path))
                self.dir(path).make_dir(overwrite, clear=False, fill=True, check_only=check_only)

            # Then create the target folder.
            if not check_only:
                os.mkdir(path)

    def raw_copy(self, path, destination):
        """
        Copy from a specific path to another specific path, with no validation.

        :param path: The path to operate on.
        :param destination: The path to copy to.
        :return: None
        """
        path = self.check_path(path)
        if destination.connection == self:
            shutil.copy2(path, str(abs(destination)))
        else:
            super().raw_copy(path, destination)
