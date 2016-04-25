"""
Automation framework.
"""


from . import abc, db, fs, notifications, security
from . import configurations, context, exceptions, plugins, strings


__author__ = 'Aaron Hosford'
__version__ = '0.0'


# noinspection PyProtectedMember
plugins.load_plugins()
