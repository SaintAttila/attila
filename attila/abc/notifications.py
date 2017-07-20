"""
Interface definition for notifiers.
"""


import datetime
import string


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
    def interpolate(template, args, kwargs):
        """
        Interpolate the given keyword arguments into a string template, handling the standard
        notification parameters in a uniform way for all notifiers.

        :param template: A string template.
        :param args: The positional arguments to interpolate into the template.
        :param kwargs: The keyword arguments to interpolate into the template.
        :return: The interpolated string.
        """

        verify_type(template, str)
        verify_type(kwargs, (dict, defaultdict))

        # TODO: Other defaults?
        if 'time' not in kwargs:
            kwargs.update(time=datetime.datetime.now())

        # The defaultdict class doesn't work with str.format,
        # so we have to parse it ourselves and add the keys.
        formatter = string.Formatter()
        for _, name, _, _ in formatter.parse(template):
            if name and name not in kwargs:
                kwargs[name] = None

        # noinspection PyBroadException
        try:
            return template.format(*args, **kwargs)
        except Exception:
            # It's important that this never fails because it's used to report errors.
            return template + ' (args: %r, kwargs: %r)' % (args, kwargs)

    # TODO: Normalize this interface. It should take an optional message, then *args and **kwargs used for 
    #       interpolation, and finally a keyword ony optional attachments list. All subclasses and their uses will also
    #       have to be updated.
    @abstractmethod
    def __call__(self, *args, attachments=None, **kwargs):
        """
        Send a notification on this notifier's channel.

        :param attachments: The file attachments, if any, to include in the notification.
        :return: None
        """
        raise NotImplementedError()
