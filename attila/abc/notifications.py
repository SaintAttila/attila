import configparser

from abc import ABCMeta, abstractmethod


from ..plugins import load_channel_from_config


__all__ = [
    'Notification',
    'Channel',
    'Notifier',
]


class Notification:
    pass


class Channel(metaclass=ABCMeta):
    """
    Abstract base class for notification channels. New channel types should support this interface and inherit from
    this class.
    """

    def __del__(self):
        self.close()

    @abstractmethod
    def send(self, notification):
        """
        Send a notification on this channel.

        :param notification: The notification to be sent on this channel.
        :return: None
        """
        raise NotImplementedError()

    def close(self):
        pass


class Notifier(metaclass=ABCMeta):
    """
    A notifier acts as a template for notifications, formatting the objects it is given into a standardized template
    and sending the resulting notification on to a particular channel.
    """

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        channel_name = config['Channel']
        channel = load_channel_from_config(config, channel_name)
        return cls(channel)

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