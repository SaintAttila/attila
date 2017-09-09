"""
Automation framework.
"""


from . import abc, db, fs, notifications, security
from . import configurations, context, exceptions, plugins, strings


__version__ = '1.11.2'

__author__ = 'Aaron Hosford'
__author_email__ = 'hosford42@gmail.com'
__description__ = 'Attila: A Python Automation Framework'
__long_description__ = __doc__
__license__ = 'MIT (https://opensource.org/licenses/MIT)'
__install_requires__ = [
    # 3rd-party
    'cryptography',
    'pywin32',
    'requests',
    'setuptools',
    'wmi',

    # In-house
    'infotags',
    'sql_dialects>=0.1',
]
__url__ = 'https://scmgr.eams.ericsson.net/PythonLibs/Attila'
__packages__ = [
    'attila',
    'attila.abc',
    'attila.db',
    'attila.fs',
    'attila.generation',
    'attila.notifications',
    'attila.security',
    'test_attila',
]
__package_data__ = {
    'attila': ['attila.ini'],
    'attila.generation': [
        '_template/*',
        '_template/.gitignore_template',  # This is skipped by '_template/*' for some reason
        '_template/package/*'
    ]
}
__entry_points__ = {'console_scripts': ['new_attila_package = attila.generation:main']}


plugins.load_plugins()
