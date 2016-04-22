"""
attila
======

Automation framework.
"""

from . import abc
from . import configurations
from . import context
from . import db
from . import exceptions
from . import fs
from . import notifications
from . import plugins
from . import processes
from . import progress
from . import security
from . import strings
from . import threads
from . import utility
from . import windows


__author__ = 'Aaron Hosford'
__version__ = '0.0.0'
__all__ = [
    'abc',
    'configurations',
    'context',
    'db',
    'exceptions',
    'fs',
    'notifications',
    'plugins',
    'processes',
    'progress',
    'security',
    'strings',
    'threads',
    'utility',
    'windows',
]


# noinspection PyProtectedMember
plugins.load_plugins()
