"""
Bindings for sending notifications to Python callbacks.
"""


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier

from ..configurations import ConfigManager, load_global_function
from ..exceptions import verify_type
from ..plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'CallbackNotifier',
]


@config_loader
class CallbackNotifier(Notifier, Configurable):
    """
    A callback channel passes incoming notifications to an arbitrary Python callback. It allows us
    to wrap Python functions in the notification channel interface so we can easily interchange
    them.
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
        assert isinstance(manager, ConfigManager)
        verify_type(value, str, non_empty=True)

        return cls(*args, callback=load_global_function(value), **kwargs)

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

        function = manager.load_option(section, 'Function', load_global_function)

        return cls(*args, callback=function, **kwargs)

    def __init__(self, callback):
        assert callable(callback)

        super().__init__()

        self._callback = callback

    @property
    def callback(self):
        """The function called by this notifier."""
        return self._callback

    def __call__(self, *args, **kwargs):
        """
        Send a notification on this notifier's channel.

        :return: None
        """
        self._callback(*args, **kwargs)
