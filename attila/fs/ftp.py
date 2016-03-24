"""
attila.ftp
==========

File Transfer Protocol functionality
"""


import configparser
import ftplib
import os
import socket


from . import files
from .. import security
from .. import strings

from .files import Path, ProxyFile


__all__ = [
    'FTPConnector',
    'ftp_connection',
]


DEFAULT_FTP_PORT = 21


class FTPConnector(files.FSConnector):
    """
    Stores the FTP connection information as a single object which can then be passed around instead of using multiple
    parameters to a function.
    """

    def __init__(self, server=None, credential=None, passive=True, initial_cwd=None):
        if server is None:
            port = DEFAULT_FTP_PORT
        else:
            assert isinstance(server, str)
            assert server
            server, port = strings.split_port(server, DEFAULT_FTP_PORT)
        if credential is not None:
            assert credential.user and credential.password
        assert passive == bool(passive)

        super().__init__(ftp_connection, initial_cwd)

        self._server = server
        self._port = port
        self._credential = credential if credential else None
        self._passive = passive

    def is_configured(self):
        return self._server is not None and self._credential is not None

    def configure(self, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)

        super().configure(config, section)

        config_section = config[section]

        server = config_section['Server']
        passive = config.getboolean(section, 'Passive', fallback=True)

        credential = security.Credential.load_from_config(config, section)

        self._server, self._port = strings.split_port(server, DEFAULT_FTP_PORT)
        self._passive = passive
        self._credential = credential

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
        return self._server

    @property
    def port(self):
        return self._port

    @property
    def credential(self):
        return self._credential

    @property
    def passive(self):
        return self._passive

    def connection(self):
        return super().connection()


# noinspection PyPep8Naming,PyAbstractClass
class ftp_connection(files.fs_connection):

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
        assert not self.is_open

        user, password = self._connector.credential

        self._session = ftplib.FTP()
        self._session.set_pasv(self._connector.passive)
        self._session.connect(self._connector.server, self._connector.port)
        self._session.login(user, password)

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
        assert self.is_open

        mode = mode.lower()
        path = self.check_path(path)

        # We can't work directly with an FTP file. Instead, we will create a temp file and return it as a proxy.
        temp_path = files.local_fs_connection.get_temp_file_path(self.name(path))

        # If we're not truncating the file, then we'll need to copy down the data.
        if mode not in ('w', 'wb'):
            self._download(path, temp_path)

        if mode in ('r', 'rb'):
            writeback = None
        else:
            writeback = self._upload

        return ProxyFile(Path(path, self), mode, buffering, encoding, errors, newline, closefd, opener,
                         proxy_path=temp_path, writeback=writeback)

    def list(self, path, pattern='*'):
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
        assert self.is_open
        path = self.check_path(path)

        dir_path, file_name = os.path.split(path)
        with Path(dir_path, self):
            return self._session.size(file_name)

    def remove(self, path):
        assert self.is_open
        path = self.check_path(path)

        dir_path, file_name = os.path.split(path)
        with Path(dir_path, self):
            self._session.delete(file_name)

    def rename(self, path, new_name):
        assert self.is_open
        path = self.check_path(path)
        assert new_name and isinstance(new_name, str)

        dir_path, file_name = os.path.split(path)
        if file_name != new_name:
            with Path(dir_path, self):
                self._session.rename(file_name, new_name)

    def is_dir(self, path):
        assert self.is_open
        path = self.check_path(path)

        # noinspection PyBroadException
        try:
            with Path(path, self):
                return True
        except Exception:
            return False

    def is_file(self, path):
        assert self.is_open
        path = self.check_path(path)

        # noinspection PyBroadException
        try:
            self.size(path)
            return True
        except Exception:
            return False
