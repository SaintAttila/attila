"""
info.py
=======

Attila package information for use by setup.py and packaging utilities.
"""

import os
import sys
from importlib.machinery import SourceFileLoader


# -----------------------------------------------------------------------------
# This should be the only line that has to change when reusing info.py for new
# modules/packages.
name = 'attila'
# -----------------------------------------------------------------------------


# Load the module/package
path = os.path.join(os.path.abspath(os.path.dirname(__file__)), name)
if os.path.isdir(path):
    import_path = os.path.join(path, '__init__.py')
else:
    path += '.py'
    import_path = path
if name in sys.modules:
    del sys.modules[name]
module = SourceFileLoader(name, import_path).load_module()


# Extract the info from the module/package
info = {
    'name': name,
    'path': path,
    'import_path': import_path,
    'module': module,
    'author': module.__author__,
    'author_email': getattr(
        module,
        '__author_email__',
        '.'.join(module.__author__.split()) + '@Ericsson.com'  # Default
    ),
    'version': module.__version__,
    'doc': module.__doc__
}
