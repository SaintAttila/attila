"""
Notification parameter-related functionality.
"""


import getpass
import datetime
import os
import socket
import traceback


from ..context import get_entry_point_name, get_entry_point_version, auto_context
from ..exceptions import verify_type


START_EVENT = 'start'
END_EVENT = 'end'
SUCCESS_EVENT = 'success'
FAILURE_EVENT = 'failure'
EXCEPTION_EVENT = 'exception'
WARNING_EVENT = 'warning'
INFORMATION_EVENT = 'information'
OTHER_EVENT = 'other'

EVENT_TYPES = frozenset({
    START_EVENT,
    END_EVENT,
    SUCCESS_EVENT,
    FAILURE_EVENT,
    EXCEPTION_EVENT,
    WARNING_EVENT,
    INFORMATION_EVENT,
    OTHER_EVENT,
})


# time: The time of the notification.
def general_notification_parameters(event, time=None):
    """
    Return a dictionary containing the general parameters that attila always provides to every notifier
    it calls directly.
    """

    verify_type(event, str, non_empty=True)
    if event not in EVENT_TYPES:
        raise ValueError(event)

    verify_type(time, datetime.datetime, allow_none=True)

    context = auto_context.current()

    return dict(
        host=socket.gethostname(),
        user=getpass.getuser(),
        pid=os.getpid(),
        process=get_entry_point_name(),
        version=get_entry_point_version(),
        event=event,
        time=datetime.datetime.now() if time is None else time,
        testing=context.testing if context else False
    )


def notification_parameters(event, task=None, message=None, exc_info=None, args=None, kwargs=None, time=None):
    """
    Return a dictionary containing all the standard parameters that attila should provide to notifiers
    it calls directly.
    """
    results = general_notification_parameters(event, time)

    if task is not None:
        verify_type(task, str, non_empty=True)
        results.update(task=task)

    if task is not None or message is not None:
        verify_type(message, str, non_empty=True, allow_none=True)
        results.update(message=message)

    if event == EXCEPTION_EVENT:
        verify_type(exc_info, tuple, non_empty=True)
        if len(exc_info) != 3 or any(item is None for item in exc_info):
            raise ValueError(exc_info)
        results.update(
            exc_info=exc_info,
            traceback=''.join(traceback.format_exception(*exc_info))
        )
    else:
        assert exc_info is None

    if args is not None:
        assert event == EXCEPTION_EVENT
        verify_type(args, tuple)
        verify_type(kwargs, dict)
        results.update(
            args=args,
            kwargs=kwargs
        )
    else:
        assert kwargs is None

    return results
