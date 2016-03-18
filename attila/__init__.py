"""
attila
======

Automation framework.
"""

from . import notifications
from . import emails
from . import plugins


__author__ = 'Aaron Hosford'
__version__ = '0.0.0'


# noinspection PyProtectedMember
plugins._load_plugins()
