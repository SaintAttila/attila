"""
attila.notifications
====================

Base classes and null implementations for notification functionality.
"""
from abc import ABCMeta, abstractmethod

__author__ = 'Aaron Hosford'


class Channel(metaclass=ABCMeta):
    """
    Abstract base class for notification channels. New channel types should support this interface and inherit from
    this class.
    """

    @abstractmethod
    def send(self, notification):
        """
        Send a notification on this channel.

        :param notification: The notification to be sent on this channel.
        :return: None
        """
        raise NotImplementedError()


class Notifier(metaclass=ABCMeta):
    """
    A notifier acts as a template for notifications, formatting the objects it is given into a standardized template
    and sending the resulting notification on to a particular channel.
    """

    def __init__(self, channel):
        assert isinstance(channel, Channel)
        self._channel = channel

    @property
    def channel(self):
        """The channel this notifier sends on."""
        return self._channel

    @abstractmethod
    def build_notification(self, *args, **kwargs):
        """
        Construct a notification from the arguments passed to the send() method.
        """
        raise NotImplementedError()

    def send(self, *args, **kwargs):
        """
        Build and send a notification on this notifier's channel.
        """
        notification = self.build_notification(*args, **kwargs)
        self._channel.send(notification)


class NullChannel(Channel):
    """
    A null channel simply drops all incoming notifications, regardless of their type or content. It's useful as a
    placeholder for notifications that have been turned off.
    """

    def send(self, notification):
        """
        Send a notification on this channel.

        :param notification: The notification to be sent on this channel.
        :return: None
        """
        pass  # Just ignore the notification, without complaint.


class NullNotifier(Notifier):
    """
    A null notifier simply drops all requested notifications, regardless of their content. It's useful as a placeholder
    for notifications that have been turned off.
    """

    def __init__(self, channel=None):
        super().__init__(channel or NullChannel())

    def build_notification(self, *args, **kwargs):
        """
        Construct a notification from the arguments passed to the send() method.
        """
        return None

    def send(self, *args, **kwargs):
        """
        Build and send a notification on this notifier's channel.
        """
        pass  # Just ignore all requests, without complaint.
