"""
attila.abc.notifications
========================

Interface definition for notifiers.
"""


from abc import ABCMeta, abstractmethod


__all__ = [
    'Notifier',
]


class Notifier(metaclass=ABCMeta):
    """
    A notifier acts as a template for notifications, formatting the objects it is given into a
    standardized template and sending the resulting notification on to a particular channel.
    """

    @abstractmethod
    def __call__(self, *args, attachments=None, **kwargs):
        """
        Send a notification on this notifier's channel.

        :param attachments: The file attachments, if any, to include in the notification.
        :return: None
        """
        raise NotImplementedError()
