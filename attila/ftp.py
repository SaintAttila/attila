"""
attila.ftp
==========

File Transfer Protocol functionality
"""


import configparser
import ftplib
import os
import socket


import attila.security
import attila.strings


class FTPConnectionInfo:
    """
    Stores the FTP connection information as a single object which can then be passed around instead of using multiple
    parameters to a function.
    """

    @classmethod
    def load_from_config(cls, config, section):
        """
        Load the FTP connection info from a section in a config file.

        :param config: A configparser.ConfigParser instance.
        :param section: The section to load the connection info from.
        :return: An FTPConnectionInfo instance.
        """

        assert isinstance(config, configparser.ConfigParser)

        config_section = config[section]

        server = config_section['Server']
        passive = config.getboolean(section, 'Passive', fallback=True)

        # This has to be imported here because the security module depends on this one.
        credential = attila.security.Credential.load_from_config(config, section)

        return cls(server, credential, passive)

    def __init__(self, server, credential, passive=True):
        assert isinstance(server, str)
        assert server

        assert credential.user and credential.password

        assert passive == bool(passive)

        server, port = attila.strings.split_port(server, 21)

        self._server = server
        self._port = port
        self._credential = credential if credential else None
        self._passive = passive

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

    def connect(self):
        return FTPConnection(self)

    def __repr__(self):
        args = [repr(self._server + ':' + str(self._port)), repr(self._credential)]
        if not self._passive:
            args.append('passive=False')
        return type(self).__name__ + '(' + ', '.join(args) + ')'


class FTPTempWD:
    """
    All this class does is temporarily change the working directory of an FTP connection, and then change it back. It's
    meant for use in a with statement. It only exists to allow FTPConnection to implement the
    temporary_working_directory(path) method.
    """

    def __init__(self, connection, folder):
        assert isinstance(connection, FTPConnection)
        assert isinstance(folder, str)
        self.connection = connection
        self.folder = folder
        self.previous_folder = None

    def __enter__(self):
        self.previous_folder = None
        if self.folder:
            previous_folder = self.connection.getcwd()
            if previous_folder != self.folder:
                self.previous_folder = previous_folder
                self.connection.chdir(self.folder)
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_folder is not None and self.connection.getcwd() != self.previous_folder:
            self.connection.chdir(self.previous_folder)
        return False  # Do not suppress exceptions.


class FTPConnection:

    def __init__(self, connection_info):
        """
        Create a new FTPConnection instance.

        Example:
            # Get a connection to the FTP server.
            connection = FTPConnection(connection_info)
        """

        assert isinstance(connection_info, FTPConnectionInfo)

        self._connection_info = connection_info
        self._session = None

        self.open()

    @property
    def connection_info(self):
        return self._connection_info

    @property
    def is_open(self):
        if self._session is None:
            return False
        try:
            self._session.voidcmd('NOOP')
        except (socket.error, IOError):
            # noinspection PyBroadException
            try:
                self.close()
            except Exception:
                pass
        return self._session is not None

    def open(self):
        if self.is_open:
            return

        user, password = self._connection_info.credential

        self._session = ftplib.FTP()
        self._session.set_pasv(self._connection_info.passive)
        self._session.connect(self._connection_info.server, self._connection_info.port)
        self._session.login(user, password)

    def close(self):
        """Close the FTP connection"""
        if self.is_open:
            # noinspection PyBroadException
            try:
                self._session.quit()  # The polite way
            except Exception:
                self._session.close()  # The rude way
            finally:
                self._session = None  # The close your eyes and pretend way

    def temporary_working_directory(self, folder):
        """
        Use with a 'with' statement to temporarily change the current working directory, and then automatically change
        it back afterward even if there's an error. Note that simply calling this function does nothing, if you don't
        use it within a 'with' statement.

        Example Usage:
            with connection.temporary_working_directory(folder_path):
                # Do stuff with CWD == folder_path.
            # Now CWD is set back to whatever it was before.

        :param folder: The folder to temporarily set as the working directory.
        :return: A context manager, usable in a 'with' statement.
        """
        return FTPTempWD(self, folder)

    def getcwd(self):
        assert self.is_open
        return self._session.pwd()

    def chdir(self, folder):
        assert self.is_open
        self._session.cwd(folder)

    def __enter__(self):
        return self  # The connection is automatically opened when it's created, so there's nothing to do.

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False  # Do not suppress exceptions

    def download(self, remote_path, local_path=None, overwrite=False):
        assert self.is_open

        dir_path, file_name = os.path.split(remote_path)

        if local_path is None:
            local_path = file_name

        if not overwrite and os.path.exists(local_path):
            raise FileExistsError(local_path)

        with self.temporary_working_directory(dir_path):
            with open(local_path, 'wb') as local_file:
                self._session.retrbinary("RETR " + file_name, local_file.write)

    def upload(self, local_path, remote_path=None, overwrite=False):
        assert self.is_open

        if remote_path is None:
            remote_path = os.path.basename(local_path)

        dir_path, file_name = os.path.split(remote_path)

        with self.temporary_working_directory(dir_path):
            if not overwrite and file_name in self.list_files():
                raise FileExistsError(remote_path)
            with open(local_path, 'rb') as local_file:
                self._session.retrbinary("STOR " + file_name, local_file)

    def list_files(self, folder=None):
        assert self.is_open

        with self.temporary_working_directory(folder or ''):
            try:
                return self._session.nlst()
            except Exception as exc:
                if '550 No files found.' in str(exc):
                    return []
                raise

    def get_size(self, path):
        assert self.is_open

        dir_path, file_name = os.path.split(path)
        with self.temporary_working_directory(dir_path):
            return self._session.size(file_name)

    def remove(self, path):
        assert self.is_open

        dir_path, file_name = os.path.split(path)
        with self.temporary_working_directory(dir_path):
            self._session.delete(file_name)

    def rename(self, path, new_name):
        assert self.is_open

        dir_path, file_name = os.path.split(path)
        with self.temporary_working_directory(dir_path):
            self._session.rename(file_name, new_name)

    def is_dir(self, path):
        assert self.is_open

        # noinspection PyBroadException
        try:
            with self.temporary_working_directory(path):
                return True
        except Exception:
            return False

    def is_file(self, path):
        assert self.is_open

        # noinspection PyBroadException
        try:
            self.get_size(path)
            return True
        except Exception:
            return False
