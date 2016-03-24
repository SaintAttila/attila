"""
attila
======

Automation framework.
"""

from . import abc
from . import db
from . import emails
from . import env
from . import error_handling
from . import fs
from . import notifications
from . import plugins
from . import processes
from . import progress
from . import resources
from . import security
from . import strings
from . import threads
from . import utility
from . import windows


__author__ = 'Aaron Hosford'
__version__ = '0.0.0'

__all__ = [
    'abc',
    'db',
    'emails',
    'env',
    'error_handling',
    'fs',
    'notifications',
    'plugins',
    'processes',
    'progress',
    'resources',
    'security',
    'strings',
    'threads',
    'utility',
    'windows',
]


# noinspection PyProtectedMember
plugins.load_plugins()
