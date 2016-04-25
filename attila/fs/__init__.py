"""
File system-related functionality
"""


from ..abc.files import Path

from . import ftp, http, local, proxies, stdio, temp


__author__ = 'Aaron Hosford'
__all__ = [
    'ftp',
    'http',
    'local',
    'proxies',
    'stdio',
    'temp',
]


# Set the default new_instance to the local file system.
Path.set_default_connection(local.local_fs_connection())
