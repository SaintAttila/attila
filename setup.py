"""
setup.py
========

Setup script for attila package.
"""

import os
import sys

from setuptools import setup

try:
    # noinspection PyUnresolvedReferences
    import infotags
except ImportError:
    print("This setup script depends on infotags. Please install infotags using the command, "
          "'pip install infotags' and then run this setup script again.")
    sys.exit(2)


PACKAGE_NAME = 'attila'


cwd = os.getcwd()
if os.path.dirname(__file__):
    os.chdir(os.path.dirname(__file__))
try:
    info = infotags.get_info(PACKAGE_NAME)

    # setup() doesn't expect this key.
    if 'doc' in info:
        del info['doc']

    setup(**info)
finally:
    os.chdir(cwd)
