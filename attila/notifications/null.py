"""
Bindings for silently dropping notifications.
"""


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier
from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'NullNotifier',
]


@config_loader
class NullNotifier(Notifier, Configurable):
    """
    A null notifier simply drops all requested notifications, regardless of their content. It's
    useful as a placeholder for notifications that have been turned off.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(manager, ConfigManager)
        verify_type(value, str)

        assert value.lower() in ('', 'null', 'none')

        return cls(*args, **kwargs)

    @classmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a class instance from a config section.

        :param manager: A ConfigManager instance.
        :param section: The name of the section.
        :return: A new instance of this class.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)
        verify_type(section, str, non_empty=True)

        pass  # Nothing to configure...

        return cls(*args, **kwargs)

    def __call__(self, *args, attachments=None, **kwargs):
        """
        Build and __call__ a notification on this notifier's channel.
        """
        pass  # Just ignore all requests, without action or complaint.
