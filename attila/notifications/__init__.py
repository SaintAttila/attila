"""
attila.notifications
====================

Built-in notification-related types and instances.
"""


from ..abc.notifications import Notification, Channel, Notifier
from . import emails
from . import null
from . import raw


__all__ = [
    'Notification',
    'Channel',
    'Notifier',
    'emails',
    'null',
    'raw',
    'NULL_CHANNEL',
    'NULL_NOTIFIER',
    'STDOUT_CHANNEL',
    'STDOUT_NOTIFIER',
    'STDERR_CHANNEL',
    'STDERR_NOTIFIER',
]


# Default plugin instances. See http://stackoverflow.com/a/9615473/4683578 for an explanation of how plugins work in the
# general case. These instances will be registered by the entry_points parameter in setup.py. Other, separately
# installable packages can register their own channel types, channels, and notifiers using the entry_points parameter
# from this package's setup.py as an example. They will be available by name during parsing of config files for
# automations built using attila.
NULL_CHANNEL = null.NullChannel()
NULL_NOTIFIER = null.NullNotifier()
STDOUT_CHANNEL = raw.FileChannel('stdout')
STDOUT_NOTIFIER = raw.RawNotifier(STDOUT_CHANNEL)
STDERR_CHANNEL = raw.FileChannel('stderr')
STDERR_NOTIFIER = raw.RawNotifier(STDERR_CHANNEL)
