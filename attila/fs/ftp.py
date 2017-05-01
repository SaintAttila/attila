"""
FTP file system support
"""


import ftplib
import os
import socket
import time

from distutils.util import strtobool
from urllib.parse import urlparse


from .. import strings
from . import local

from ..abc.files import Path, FSConnector, fs_connection

from ..configurations import ConfigManager
from ..exceptions import verify_type, OperationNotSupportedError
from ..plugins import config_loader, url_scheme
from ..security import credentials
from .proxies import ProxyFile


__author__ = 'Aaron Hosford'
__all__ = [
    'FTPConnector',
    'ftp_connection',
]


DEFAULT_FTP_PORT = 21
INT_TIME_FORMAT = '%Y%m%d%H%M%S'
FLOAT_TIME_FORMAT = '%Y%m%d%H%M%S.%f'


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

        if '@' in netloc:
            user, address = netloc.split('@')
        else:
            user = None
            address = netloc

        if ':' in address:
            server, port = address.split(':')
            port = int(port)
        else:
            server = address
            port = DEFAULT_FTP_PORT

        if user:
            # We do not permit passwords to be stored in plaintext in the parameter value.
            assert ':' not in user

            credential_string = user + '@' + server + '/ftp'
            credential = manager.load_value(credential_string, credentials.Credential)
        else:
            credential = None

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

    def __init__(self, server, credential=None, passive=True, initial_cwd=None):
        verify_type(server, str, non_empty=True)
        server, port = strings.split_port(server, DEFAULT_FTP_PORT)

        if credential:
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

        cwd = self.getcwd()

        self._session = ftplib.FTP()
        self._session.set_pasv(self._connector.passive)
        self._session.connect(self._connector.server, self._connector.port)

        if self._connector.credential:
            user, password, _ = self._connector.credential
            self._session.login(user, password or '')

        super().open()
        if cwd is None:
            # This forces the CWD to be refreshed.
            self.getcwd()
        else:
            # This overrides the CWD based on what it was set to before the connection was opened.
            self.chdir(cwd)

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

    def getcwd(self):
        """Get the current working directory of this FTP connection."""
        if self.is_open:
            super().chdir(self._session.pwd())
            return super().getcwd()

        return super().getcwd()

    def chdir(self, path):
        """Set the current working directory of this FTP connection."""
        super().chdir(path)
        if self.is_open:
            self._session.cwd(str(super().getcwd()))

    def _download(self, remote_path, local_path):
        assert self.is_open
        remote_path = self.check_path(remote_path)
        assert isinstance(local_path, str)

        dir_path, file_name = os.path.split(remote_path)

        with Path(dir_path, self):
            with open(local_path, 'wb') as local_file:
                self._session.retrbinary("RETR " + file_name, local_file.write)

    def _upload(self, local_path, remote_path):
        assert self.is_open
        assert isinstance(local_path, str)
        remote_path = self.check_path(remote_path)

        dir_path, file_name = os.path.split(remote_path)

        with Path(dir_path, self):
            with open(local_path, 'rb') as local_file:
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
        with local.local_fs_connection() as connection:
            temp_path = str(abs(connection.get_temp_file_path(self.name(path))))

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
            # We have to do this because we can't check if path is a directory,
            # and if we call nlst on a file name, sometimes it will just return
            # that file name in the list instead of bombing out.
            listing = [name for name in listing if self.exists(path[name])]
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

        return self._session.size(path)

    def modified_time(self, path):
        """
        Get the last time the data of file system object was modified.

        :param path: The path to operate on.
        :return: The time stamp, as a float.
        """
        assert self.is_open
        path = Path(self.check_path(path), self)
        with Path(path.dir):
            result = self._session.sendcmd('MDTM %s' % path.name)
            response_code = result.split()[0]
            if response_code != '213':
                if path.exists:
                    raise OperationNotSupportedError()
                else:
                    raise FileNotFoundError()
            timestamp = result.split()[-1]
            if '.' in timestamp:
                time_format = FLOAT_TIME_FORMAT
            else:
                time_format = INT_TIME_FORMAT
            try:
                return time.mktime(time.strptime(timestamp, time_format))
            except ValueError as exc:
                raise OperationNotSupportedError() from exc

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
                try:
                    self._session.nlst()
                except Exception as exc:
                    # Some FTP servers give an error if the directory is empty.
                    if '550 No files found.' in str(exc):
                        return True
                    else:
                        return False
                else:
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

    def join(self, *path_elements):
        """
        Join several path elements together into a single path.

        :param path_elements: The path elements to join.
        :return: The resulting path.
        """
        if path_elements:
            # There is a known Python bug which causes any TypeError raised by a generator during
            # argument interpolation with * to be incorrectly reported as:
            #       TypeError: join() argument after * must be a sequence, not generator
            # The bug is documented at:
            #       https://mail.python.org/pipermail/new-bugs-announce/2009-January.txt
            # To avoid this confusing misrepresentation of errors, I have broken this section out
            # into multiple statements so TypeErrors get the opportunity to propagate correctly.
            starting_slash = path_elements and str(path_elements[0]).startswith('/')
            path_elements = tuple(self.check_path(element).strip('/\\') for element in path_elements)
            if starting_slash:
                path_elements = ('',) + path_elements
            return Path('/'.join(path_elements), connection=self)
        else:
            return Path(connection=self)
