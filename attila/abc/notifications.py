"""
Interface definition for notifiers.
"""


import datetime

from abc import ABCMeta, abstractmethod
from collections import defaultdict


from ..exceptions import verify_type


__author__ = 'Aaron Hosford'
__all__ = [
    'Notifier',
]


class Notifier(metaclass=ABCMeta):
    """
    A notifier acts as a template for notifications, formatting the objects it is given into a
    standardized template and sending the resulting notification on to a particular channel.
    """

    @staticmethod
    def interpolate(template, args, kwargs, *, time_stamp=None):
        """
        Interpolate the given keyword arguments into a string template, handling the standard
        notification parameters in a uniform way for all notifiers.

        :param template: A string template.
        :param args: The positional arguments to interpolate into the template.
        :param kwargs: The keyword arguments to interpolate into the template.
        :param time_stamp: An optional datetime used to apply time formatting, or True to use the
            current time.
        :return: The interpolated string.
        """

        verify_type(template, str)
        verify_type(kwargs, (dict, defaultdict))

        if isinstance(time_stamp, bool):
            if time_stamp:
                time_stamp = datetime.datetime.now()
            else:
                time_stamp = None
        verify_type(time_stamp, datetime.datetime, allow_none=True)

        kwargs = defaultdict(lambda: None, **kwargs)

        if 'task' not in kwargs:
            kwargs.update(task='unspecified')

        result = (template % args).format_map(**kwargs)

        if time_stamp:
            result = time_stamp.strftime(result)

        return result

    @abstractmethod
    def __call__(self, *args, attachments=None, **kwargs):
        """
        Send a notification on this notifier's channel.

        :param attachments: The file attachments, if any, to include in the notification.
        :return: None
        """
        raise NotImplementedError()
