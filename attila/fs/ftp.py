"""
FTP file system support
"""


import ftplib
import os
import socket

from distutils.util import strtobool
from urllib.parse import urlparse


from .. import strings
from . import local

from ..abc.files import Path, FSConnector, fs_connection

from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader, url_scheme
from ..security import credentials
from .proxies import ProxyFile


__author__ = 'Aaron Hosford'
__all__ = [
    'FTPConnector',
    'ftp_connection',
]


DEFAULT_FTP_PORT = 21


@config_loader
@url_scheme('ftp')
class FTPConnector(FSConnector):
    """
    Stores the FTP connection information as a single object which can then be passed around
    instead of using multiple parameters to a function.
    """

    @classmethod
    def load_url(cls, manager, url):
        """
        Load a new Path instance from a URL string.

        The standard format for an FTP URL is "ftp://user:password@host:port/path". However, storing
        of plaintext passwords in parameters is not permitted, so the format is
        "ftp://user@host:port/path", where the password is automatically loaded from the password
        database.

        :param manager: The ConfigManager instance.
        :param url: The URL to load.
        :return: The resultant Path instance.
        """
        verify_type(manager, ConfigManager)
        verify_type(url, str)

        if '://' not in url:
            url = 'ftp://' + url
        scheme, netloc, path, params, query, fragment = urlparse(url)
        assert not params and not query and not fragment
        assert scheme.lower() == 'ftp'
        assert '@' in netloc

        user, address = netloc.split('@')

        if ':' in address:
            server, port = address.split(':')
            port = int(port)
        else:
            server = address
            port = DEFAULT_FTP_PORT

        # We do not permit passwords to be stored in plaintext in the parameter value.
        assert ':' not in user

        credential_string = user + '@' + server + '/ftp'
        credential = manager.load_value(credential_string, credentials.Credential)

        return Path(path, cls(server + ':' + str(port), credential).connect())

    @classmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)

        verify_type(section, str, non_empty=True)

        server = manager.load_option(section, 'Server', str)
        port = manager.load_option(section, 'Port', int, None)
        passive = bool(manager.load_option(section, 'Passive', strtobool, False))
        credential = manager.load_section(section, credentials.Credential)

        if port is not None:
            server = server + ':' + str(port)

        return super().load_config_section(
            manager,
            section,
            *args,
            server=server,
            credential=credential,
            passive=passive,
            **kwargs
        )

    def __init__(self, server, credential, passive=True, initial_cwd=None):
        verify_type(server, str, non_empty=True)
        server, port = strings.split_port(server, DEFAULT_FTP_PORT)

        assert credential.user

        verify_type(passive, bool)

        super().__init__(ftp_connection, initial_cwd)

        self._server = server
        self._port = port
        self._credential = credential
        self._passive = passive

    def __repr__(self):
        server_string = None
        if self._server is not None:
            server_string = self._server
            if self._port != DEFAULT_FTP_PORT:
                server_string += ':' + str(self._port)
        args = [repr(server_string), repr(self._credential)]
        if not self._passive:
            args.append('passive=False')
        return type(self).__name__ + '(' + ', '.join(args) + ')'

    @property
    def server(self):
        """The DNS name or IP address of the remote server."""
        return self._server

    @property
    def port(self):
        """The remote server's port."""
        return self._port

    @property
    def credential(self):
        """The use name/password used to connect to the remote server."""
        return self._credential

    @property
    def passive(self):
        """Whether to access the server in passive mode."""
        return self._passive

    def connect(self):
        """Create a new connection and return it."""
        return super().connect()


# noinspection PyPep8Naming
@config_loader
class ftp_connection(fs_connection):
    """
    An ftp_connection manages the state for a connection to an FTP server, providing a
    standardized interface for interacting with remote files and directories.
    """

    @classmethod
    def get_connector_type(cls):
        """Get the connector type associated with this connection type."""
        return FTPConnector

    def __init__(self, connector):
        """
        Create a new ftp_connection instance.

        Example:
            # Get a connection to the FTP server.
            connection = ftp_connection(connector)
        """
        assert isinstance(connector, FTPConnector)
        super().__init__(connector)

        self._session = None

    @property
    def is_open(self):
        """Whether the FTP connection is currently open."""
        if self._is_open:
            try:
                self._session.voidcmd('NOOP')
            except (socket.error, IOError):
                # noinspection PyBroadException
                try:
                    self.close()
                except Exception:
                    pass
                self._is_open = False
        return super().is_open

    def open(self):
        """Open the FTP connection."""
        assert not self.is_open

        user, password, _ = self._connector.credential

        self._session = ftplib.FTP()
        self._session.set_pasv(self._connector.passive)
        self._session.connect(self._connector.server, self._connector.port)
        self._session.login(user, password or '')

    def close(self):
        """Close the FTP connection"""
        assert self.is_open

        # noinspection PyBroadException
        try:
            self._session.quit()  # The polite way
        except Exception:
            self._session.close()  # The rude way
        finally:
            self._session = None  # The close your eyes and pretend way
            self._is_open = False

    @property
    def cwd(self):
        """The current working directory of this FTP connection."""
        assert self.is_open
        return Path(self._session.pwd(), self)

    @cwd.setter
    def cwd(self, path):
        assert self.is_open
        path = self.check_path(path)
        self._session.cwd(path)

    def _download(self, remote_path, local_path):
        assert self.is_open
        remote_path = self.check_path(remote_path)
        assert isinstance(local_path, str)

        dir_path, file_name = os.path.split(remote_path)

        with Path(dir_path, self):
            with open(abs(local_path), 'wb') as local_file:
                self._session.retrbinary("RETR " + file_name, local_file.write)

    def _upload(self, local_path, remote_path):
        assert self.is_open
        assert isinstance(local_path, str)
        remote_path = self.check_path(remote_path)

        dir_path, file_name = os.path.split(remote_path)

        with Path(dir_path, self):
            with open(abs(local_path), 'rb') as local_file:
                self._session.retrbinary("STOR " + file_name, local_file)

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
        assert self.is_open

        mode = mode.lower()
        path = self.check_path(path)

        # We can't work directly with an FTP file. Instead, we will create a temp file and return it
        # as a proxy.
        temp_path = local.local_fs_connection.get_temp_file_path(self.name(path))

        # If we're not truncating the file, then we'll need to copy down the data.
        if mode not in ('w', 'wb'):
            self._download(path, temp_path)

        if mode in ('r', 'rb'):
            writeback = None
        else:
            writeback = self._upload

        return ProxyFile(Path(path, self), mode, buffering, encoding, errors, newline, closefd,
                         opener, proxy_path=temp_path, writeback=writeback)

    def list(self, path, pattern='*'):
        """
        Return a list of the names of the files and directories appearing in this folder.

        :param path: The path to operate on.
        :param pattern: A glob-style pattern against which names must match.
        :return: A list of matching file and directory names.
        """
        assert self.is_open
        path = Path(self.check_path(path), self)
        with path:
            try:
                listing = self._session.nlst()
            except Exception as exc:
                # Some FTP servers give an error if the directory is empty.
                if '550 No files found.' in str(exc):
                    listing = []
                else:
                    raise
        if pattern == '*':
            return listing
        else:
            pattern = strings.glob_to_regex(pattern)
            return [name for name in listing if pattern.match(name)]

    def size(self, path):
        """
        Get the size of the file.

        :param path: The path to operate on.
        :return: The size in bytes.
        """
        assert self.is_open
        path = self.check_path(path)

        dir_path, file_name = os.path.split(path)
        with Path(dir_path, self):
            return self._session.size(file_name)

    def remove(self, path):
        """
        Remove the folder or file.

        :param path: The path to operate on.
        """
        assert self.is_open
        path = self.check_path(path)

        dir_path, file_name = os.path.split(path)
        with Path(dir_path, self):
            self._session.delete(file_name)

    def rename(self, path, new_name):
        """
        Rename a file object.

        :param path: The path to be operated on.
        :param new_name: The new name of the file object, as as string.
        :return: None
        """
        assert self.is_open
        path = self.check_path(path)
        assert new_name and isinstance(new_name, str)

        dir_path, file_name = os.path.split(path)
        if file_name != new_name:
            with Path(dir_path, self):
                self._session.rename(file_name, new_name)

    def is_dir(self, path):
        """
        Determine if the path refers to an existing directory.

        :param path: The path to operate on.
        :return: Whether the path is a directory.
        """
        assert self.is_open
        path = self.check_path(path)

        # noinspection PyBroadException
        try:
            with Path(path, self):
                return True
        except Exception:
            return False

    def is_file(self, path):
        """
        Determine if the path refers to an existing file.

        :param path: The path to operate on.
        :return: Whether the path is a file.
        """
        assert self.is_open
        path = self.check_path(path)

        # noinspection PyBroadException
        try:
            self.size(path)
            return True
        except Exception:
            return False
