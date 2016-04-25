"""
HTTP file system support
"""

import ctypes

from urllib.parse import urlparse

from ..abc.files import FSConnector, fs_connection
from ..abc.files import Path
from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader, url_scheme
from .proxies import ProxyFile
from .local import local_fs_connection

__author__ = 'Aaron Hosford'
__all__ = [
    'HTTPFSConnector',
    'http_fs_connection',
]


# TODO: This doesn't appear to be used. Should it be? If not, remove it.
# http://msdn.microsoft.com/en-us/library/ie/ms775145(v=vs.85).aspx
INET_E_DOWNLOAD_FAILURE = 0x800C0008


@config_loader
@url_scheme('http')
class HTTPFSConnector(FSConnector):
    """
    Stores the HTTP new_instance information.
    """

    @classmethod
    def load_url(cls, manager, url):
        """
        Load a new Path instance from a URL string.

        The standard format for an HTTP URL is "http://host:port/path".

        :param manager: The ConfigManager instance.
        :param url: The URL to load.
        :return: The resultant Path instance.
        """
        verify_type(manager, ConfigManager)
        verify_type(url, str)

        if '://' not in url:
            url = 'http://' + url
        scheme, netloc, path, params, query, fragment = urlparse(url)
        assert scheme.lower() == 'http'
        assert '@' not in netloc

        return Path(url, cls().connect())

    def __init__(self, initial_cwd=None):
        super().__init__(http_fs_connection, initial_cwd)

    def connect(self):
        """Create a new connection and return it."""
        return super().connect()


# noinspection PyPep8Naming
@config_loader
class http_fs_connection(fs_connection):
    """
    An http_fs_connection handles the underlying interactions with a remote file system accessed via
    HTTP on behalf of Path instances.
    """

    @classmethod
    def get_connector_type(cls):
        """Get the connector type associated with this connection type."""
        return HTTPFSConnector

    def __init__(self, connector=None):
        if connector is None:
            connector = HTTPFSConnector()
        else:
            assert isinstance(connector, HTTPFSConnector)
        super().__init__(connector)
        super().open()  # http fs connections are always open.

    def open(self):
        """Open the new_instance."""
        pass  # http fs connections are always open.

    def close(self):
        """Close the new_instance"""
        pass  # http fs connections are always open.

    def __repr__(self):
        return type(self).__name__ + '()'

    def __eq__(self, other):
        if not isinstance(other, fs_connection):
            return NotImplemented
        return isinstance(other, http_fs_connection)

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

        if mode not in ('r', 'rb'):
            raise ValueError("Unsupported mode: " + repr(mode))

        # We can't work directly with an HTTP file using URLDownloadToFileW(). Instead, we will
        # create a temp file and return it as a proxy.
        temp_path = local_fs_connection.get_temp_file_path(self.name(path))

        # http://msdn.microsoft.com/en-us/library/ie/ms775123(v=vs.85).aspx
        result = ctypes.windll.urlmon.URLDownloadToFileW(0, path, str(temp_path), 0, 0)

        if result == 1:
            raise MemoryError(
                "Insufficient memory available to download " + path + ". (Return code 1)"
            )
        elif result != 0:
            raise RuntimeError(
                "Unspecified error while trying to download " + path + ". (Return code " +
                str(result) + ")"
            )
        elif not temp_path.is_file:
            raise FileNotFoundError(
                "File appeared to download successfully from " + path +
                " but could not be found afterward."
            )

        return ProxyFile(Path(path, self), mode, buffering, encoding, errors, newline, closefd,
                         opener, proxy_path=temp_path, writeback=None)
