"""
Wrapper for ensuring mutual exclusion to resources during notifications.
"""


import logging


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier

from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader
from ..threads import mutex


__author__ = 'Aaron Hosford'
__all__ = [
    'CompositeNotifier',
]


log = logging.getLogger(__name__)


@config_loader
class MutexNotifier(Notifier, Configurable):
    """
    Wraps other notifier types and holds a mutex during notification.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        raise NotImplementedError()

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

        mutex_name = manager.load_option(section, 'Mutex', str)
        verify_type(mutex_name, str, non_empty=True)

        if manager.has_option(section, 'Wrapped Type'):
            loader = manager.load_option(section, 'Wrapped Type')
            notifier = manager.load_section(section, loader)
        else:
            notifier = manager.load_option(section, 'Wrapped Notifier')
        verify_type(notifier, Notifier)

        return cls(
            *args,
            wrapped=notifier,
            mutex_name=mutex_name,
            **kwargs
        )

    def __init__(self, wrapped, mutex_name):
        verify_type(wrapped, Notifier)
        verify_type(mutex_name, str, non_empty=True)

        super().__init__()

        self._wrapped = wrapped
        self._mutex_name = mutex_name

    @property
    def wrapped(self):
        """The notifier this mutex notifier wrapper protects."""
        return self._wrapped

    @property
    def mutex_name(self):
        """The name of the mutex used to protect the wrapped notifier."""
        return self._mutex_name

    def __call__(self, *args, **kwargs):
        """
        Send a notification on this notifier's channel.

        :return: None
        """
        with mutex(self._mutex_name):
            self._wrapped(*args, **kwargs)
