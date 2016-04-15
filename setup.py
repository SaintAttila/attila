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
        license='Ericsson Proprietary - Do Not Distribute',  # TODO: This will be open source. Need to pick a license.
        install_requires=[
            # 3rd-party:
            'appdirs',

            # In-house:
        ],
        entry_points={
            'attila.channel_type': [
                'callback = attila.notifications:CallbackNotifier',
                'log = attila.notifications:LogNotifier',
                'file = attila.notifications:FileNotifier',
                'email = attila.notifications:EmailConnector',
            ],
            'attila.channel': [
                'null = attila.notifications:NULL_CHANNEL',
                'stdout = attila.notifications:STDOUT_CHANNEL',
                'stderr = attila.notifications:STDERR_CHANNEL',
            ],
            'attila.notifier_type': [
                'raw = attila.notifications:RawNotifier',
                'email = attila.notifications:EmailNotifier',
            ],
            'attila.notifier': [
                'null = attila.notifications:NULL_NOTIFIER',
                'stdout = attila.notifications:STDOUT_NOTIFIER',
                'stderr = attila.notifications:STDERR_NOTIFIER',
            ]
        }
    )
finally:
    os.chdir(cwd)
