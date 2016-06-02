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
__requires__ = ['cryptography', 'infotags', 'pywin32', 'setuptools', 'wmi']
__url__ = 'TBD'
__version__ = '1.1'


plugins.load_plugins()
