"""
attila.fs.stdio
===============

STDIN/STDOUT/STDERR file system support
"""

import glob
import os
import shutil
import stat
import sys
import tempfile

from urllib.parse import urlparse

from ..abc.files import Path, FSConnector, fs_connection
from ..configurations import ConfigLoader
from ..exceptions import DirectoryNotEmptyError, verify_type


__all__ = [
    'STDIOFSConnector',
    'stdio_fs_connection',
]


class STDIOFSConnector(FSConnector):
    """
    Stores the STDIO files system new_instance information.
    """

    @classmethod
    def load_url(cls, config_loader, url):
        """
        Load a new Path instance from a URL string.

        There is no standard format for a stdio URL. We use "stdio://stream_name"

        :param config_loader: The ConfigLoader instance.
        :param url: The URL to load.
        :return: The resultant Path instance.
        """
        verify_type(config_loader, ConfigLoader)
        verify_type(url, str)

        if '://' not in url:
            url = 'stdio://' + url
        scheme, netloc, path, params, query, fragment = urlparse(url)
        assert not path and not params and not query and not fragment
        assert scheme.lower() == 'stdio'
        assert netloc.lower() in ('stdin', 'stdout', 'stderr')

        return Path(netloc, cls().connect())

    def __init__(self, initial_cwd=None):
        super().__init__(stdio_fs_connection, initial_cwd)

    def connect(self):
        """Create a new connection and return it."""
        return super().connect()


# noinspection PyPep8Naming,PyAbstractClass
class stdio_fs_connection(fs_connection):
    """
    stdio_fs_connection implements an interface for the STDIO file system, handling interactions with it on
    behalf of Path instances.
    """

    def __init__(self, connector=None):
        if connector is None:
            connector = STDIOFSConnector()
        else:
            assert isinstance(connector, STDIOFSConnector)
        super().__init__(connector)
        super().open()  # stdio fs connections are always open.

    def open(self):
        """Open the new_instance."""
        pass  # stdio fs connections are always open.

    def close(self):
        """Close the new_instance"""
        pass  # stdio fs connections are always open.

    def __repr__(self):
        return type(self).__name__ + '()'

    def __eq__(self, other):
        if not isinstance(other, fs_connection):
            return NotImplemented
        return isinstance(other, stdio_fs_connection)

    def abs_path(self, path):
        """
        Return an absolute form of a potentially relative path.

        :param path: The path to operate on.
        :return: The absolute path.
        """
        return Path(self.check_path(path).upper(), self)

    def is_dir(self, path):
        """
        Determine if the path refers to an existing directory.

        :param path: The path to operate on.
        :return: Whether the path is a directory.
        """
        self.check_path(path)
        return False

    def is_file(self, path):
        """
        Determine if the path refers to an existing file.

        :param path: The path to operate on.
        :return: Whether the path is a file.
        """
        return str(self.abs_path(path)) in ('STDIN', 'STDOUT', 'STDERR')

    def exists(self, path):
        """
        Determine if the path refers to an existing file object.

        :param path: The path to operate on.
        :return: Whether the path exists.
        """
        return self.is_file(path)

    def open_file(self, path, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True,
                  opener=None):
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
        path = self.abs_path(path)
        assert self.is_file(path)

        # TODO: Can we be more flexible here?
        assert mode in ('r', 'a')
        assert buffering == -1
        assert encoding is None
        assert errors is None
        assert newline is None
        assert closefd == True
        assert opener is None

        if path == 'STDIN':
            assert mode == 'r'
            return sys.stdin
        else:
            assert mode == 'a'
            if path == 'STDOUT':
                return sys.stdout
            else:
                assert path == 'STDERR'
                return sys.stderr
