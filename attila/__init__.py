"""
Automation framework.
"""


from . import abc, db, fs, notifications, security
from . import configurations, context, exceptions, plugins, strings


__author__ = 'Aaron Hosford'
__author_email__ = 'Aaron.Hosford@Ericsson.com'
__description__ = 'Saint Attila: Automation Library'
__long_description__ = __doc__
__license__ = 'MIT (https://opensource.org/licenses/MIT)'
__install_requires__ = [
    # 3rd-party
    'cryptography',
    'pywin32',
    'setuptools',
    'wmi',

    # In-house
    'infotags',
    'sql_dialects>=0.1',
]
__url__ = 'TBD'
__version__ = '1.3'
__packages__ = [
    'attila',
    'attila.abc',
    'attila.db',
    'attila.fs',
    'attila.notifications',
    'attila.security'
]
__package_data__ = {'attila': ['attila.ini']}


plugins.load_plugins()
