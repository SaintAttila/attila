import os
from setuptools import setup

# Load this library's information.
from info import info


cwd = os.getcwd()
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
        ]
    )
finally:
    os.chdir(cwd)
