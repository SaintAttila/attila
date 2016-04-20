"""
attila.notifications.null
=========================

Bindings for silently dropping notifications.
"""


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier

from ..configurations import ConfigLoader
from ..exceptions import verify_type


__all__ = [
    'NullNotifier',
]


class NullNotifier(Notifier, Configurable):
    """
    A null notifier simply drops all requested notifications, regardless of their content. It's
    useful as a placeholder for notifications that have been turned off.
    """

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param config_loader: A ConfigLoader instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(config_loader, ConfigLoader)
        verify_type(value, str)

        assert value.lower() in ('', 'null', 'none')

        return cls(*args, **kwargs)

    @classmethod
    def load_config_section(cls, config_loader, section, *args, **kwargs):
        """
        Load a class instance from a config section.

        :param config_loader: A ConfigLoader instance.
        :param section: The name of the section.
        :return: A new instance of this class.
        """
        verify_type(config_loader, ConfigLoader)
        assert isinstance(config_loader, ConfigLoader)
        verify_type(section, str, non_empty=True)

        pass  # Nothing to configure...

        return cls(*args, **kwargs)

    def __call__(self, *args, attachments=None, **kwargs):
        """
        Build and __call__ a notification on this notifier's channel.
        """
        pass  # Just ignore all requests, without action or complaint.
