"""
File system-related functionality
"""


from ..abc.files import Path

from . import ftp, http, local, proxies, stdio, temp
from ..exceptions import OperationNotSupportedError


__author__ = 'Aaron Hosford'
__all__ = [
    'ftp',
    'http',
    'local',
    'proxies',
    'stdio',
    'temp',
]


def getcwd():
    """
    Return the current working directory on the default file system. If no default
    connection is set or the default connection does not support a CWD, return None.
    """
    connection = Path.get_default_connection()
    if connection:
        try:
            with connection:
                return connection.cwd
        except OperationNotSupportedError:
            return None
    else:
        return None


# Set the default new_instance to the local file system.
Path.set_default_connection(local.local_fs_connection())
