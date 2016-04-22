"""
setup.py
========

Setup script for attila package.
"""

import os
from setuptools import setup

# Load this library's information.
from info import info


cwd = os.getcwd()
if os.path.dirname(__file__):
    os.chdir(os.path.dirname(__file__))
try:
    setup(
        # Stuff extracted from the library info:
        name=info['name'],
        author=info['author'],
        author_email=info['author_email'],
        version=info['version'],
        long_description=info['doc'],

        # Stuff we might have to set by hand if it's non-standard:
        packages=[info['name']],

        # Stuff we definitely have to set by hand:
        description="Saint Attila: Automation Library",
        license='MIT (https://opensource.org/licenses/MIT)',
        install_requires=[
            # 3rd-party:
            'appdirs',
            'cryptography',
            'wmi',

            # In-house:
        ],

        # Registration of built-in plugins. See http://stackoverflow.com/a/9615473/4683578 for an
        # explanation of how plugins work in the general case. Other, separately installable
        # packages can register their own plugins using this file as an example. They will be
        # available by name during parsing of config files for automations built using attila.
        # entry_points={
        #     'attila.config_loaders': [
        #         'ADODBConnector = attila.db.adodb:ADODBConnector',
        #         'bool = attila.strings:parse_bool',
        #         'CallbackNotifier = attila.notifications.callbacks:CallbackNotifier',
        #         'char = attila.strings:parse_char',
        #         'Credential = attila.security.credentials:Credential',
        #         'EmailAddress = attila.notifications.emails:validate_email_address',
        #         'EmailAddressList = attila.notifications.emails:to_email_address_set',
        #         'EmailConnector = attila.notifications.emails:EmailConnector',
        #         'EmailNotifier = attila.notifications.emails:EmailNotifier',
        #         'FileNotifier = attila.notifications.files:FileNotifier',
        #         'FTPConnector = attila.fs.ftp:FTPConnector',
        #         'ftp_connection = attila.fs.ftp:ftp_connection',
        #         'HTTPConnector = attila.fs.http:HTTPConnector',
        #         'http_connection = attila.fs.http:http_connection',
        #         'int = attila.strings:parse_int',
        #         'LocalFSConnector = attila.fs.local:LocalFSConnector',
        #         'local_fs_connection = attila.fs.local:local_fs_connection',
        #         'LogNotifier = attila.notifications.logs:LogNotifier',
        #         'NullNotifier = attila.notifications.null:NullNotifier',
        #         'Path = attila.abc.files:Path',
        #         'SQLiteConnector = attila.db.sqlite:SQLiteConnector',
        #         'STDIOFSConnector = attila.fs.stdio:STDIOFSConnector',
        #         'stdio_fs_connection = attila.fs.stdio:stdio_fs_connection',
        #     ]
        #     'attila.channel_type': [
        #         'callback = attila.notifications:CallbackNotifier',
        #         'log = attila.notifications:LogNotifier',
        #         'file = attila.notifications:FileNotifier',
        #         'email = attila.notifications:EmailConnector',
        #     ],
        #     'attila.channel': [
        #         'null = attila.notifications:NULL_CHANNEL',
        #         'stdout = attila.notifications:STDOUT_CHANNEL',
        #         'stderr = attila.notifications:STDERR_CHANNEL',
        #     ],
        #     'attila.notifier_type': [
        #         'raw = attila.notifications:RawNotifier',
        #         'email = attila.notifications:EmailNotifier',
        #     ],
        #     'attila.notifier': [
        #         'null = attila.notifications:NULL_NOTIFIER',
        #         'stdout = attila.notifications:STDOUT_NOTIFIER',
        #         'stderr = attila.notifications:STDERR_NOTIFIER',
        #     ]
        # }
    )
finally:
    os.chdir(cwd)
