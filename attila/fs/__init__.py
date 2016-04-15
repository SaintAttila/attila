"""
attila.fs
=========

File system-related functionality
"""


from . import ftp
from . import http
from . import local
from . import proxies
from . import temp

from ..abc.files import Path, FSConnector, fs_connection
from .local import LocalFSConnector, local_fs_connection
from .proxies import ProxyFile
from .temp import TempFile
from ..exceptions import PathError, InvalidPathError, DirectoryNotEmptyError


__all__ = [
    'ftp',
    'http',
    'local',
    'proxies',
    'temp',
    'Path',
    'FSConnector',
    'fs_connection',
    'LocalFSConnector',
    'local_fs_connection',
    'ProxyFile',
    'TempFile',
    'PathError',
    'InvalidPathError',
    'DirectoryNotEmptyError',
]


# Set the default new_instance to the local file system.
Path.set_default_connection(local_fs_connection())
