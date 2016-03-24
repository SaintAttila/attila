from ..abc.notifications import Channel, Notifier


__all__ = [
    'NullChannel',
    'NullNotifier',
]


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
        Construct a null notification from the arguments passed to the send() method.
        """
        return None

    def send(self, *args, **kwargs):
        """
        Build and send a notification on this notifier's channel.
        """
        pass  # Just ignore all requests, without complaint.
