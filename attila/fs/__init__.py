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

from ..abc.files import Path
from .local import local_fs_connection

__all__ = [
    'ftp',
    'http',
    'local',
    'proxies',
    'temp',
]


# Set the default new_instance to the local file system.
Path.set_default_connection(local_fs_connection())
