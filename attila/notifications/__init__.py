"""
attila.notifications
====================

Built-in notification-related types and instances.
"""
import attila.notifications.files
from ..abc.notifications import Notifier
from . import emails
from . import null
from . import callbacks


# TODO: Replace Channels with Connectors and then rename Notifiers to Channels.
__all__ = [
    'Notifier',
    'emails',
    'null',
    'callbacks',
    'NULL_NOTIFIER',
    'STDOUT_NOTIFIER',
    'STDERR_NOTIFIER',
]


# Default plugin instances. See http://stackoverflow.com/a/9615473/4683578 for an explanation of how plugins work in the
# general case. These instances will be registered by the entry_points parameter in setup.py. Other, separately
# installable packages can register their own channel types, channels, and notifiers using the entry_points parameter
# from this package's setup.py as an example. They will be available by name during parsing of config files for
# automations built using attila.
NULL_CHANNEL = null.NullChannel()
NULL_NOTIFIER = null.NullNotifier()
STDOUT_CHANNEL = attila.notifications.files.FileNotifier('stdout')
STDOUT_NOTIFIER = callbacks.RawNotifier(STDOUT_CHANNEL)
STDERR_CHANNEL = attila.notifications.files.FileNotifier('stderr')
STDERR_NOTIFIER = callbacks.RawNotifier(STDERR_CHANNEL)
