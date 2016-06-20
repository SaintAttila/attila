"""
Bindings for sending notifications to multiple callbacks.
"""

import logging
import sys
import traceback


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier

from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader
from ..strings import to_list_of_strings


__author__ = 'Aaron Hosford'
__all__ = [
    'CompositeNotifier',
]


log = logging.getLogger(__name__)


@config_loader
class CompositeNotifier(Notifier, Configurable):
    """
    A composite notifier passes incoming notifications to multiple callbacks.
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

        notifiers = [
            manager.load_section(notifier_name)
            for notifier_name in to_list_of_strings(value)
        ]

        for notifier in notifiers:
            verify_type(notifier, Notifier)

        return cls(
            *args,
            notifiers=notifiers,
            stop_on_error=False,
            stop_on_success=False,
            propagate_errors=True,
            error_notifier=None,
            **kwargs
        )

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

        option_names = [
            option_name.lower()
            for option_name in manager.get_options(section)
            if (option_name and
                len(option_name.split()) == 2 and
                option_name.lower().split()[0] == 'notifier' and
                option_name.split()[1].isdigit())
        ]

        option_names.sort(key=lambda option_name: int(option_name.split()[1]))

        notifiers = [
            manager.load_option(section, option_name)
            for option_name in option_names
        ]

        for notifier in notifiers:
            verify_type(notifier, Notifier)

        stop_on_error = manager.load_option(section, 'Stop On Error', bool, default=False)
        stop_on_success = manager.load_option(section, 'Stop On Success', bool, default=False)
        propagate_errors = manager.load_option(section, 'Propagate Errors', bool, default=True)

        error_notifier = manager.load_option(section, 'Error Notifier', default=None)
        verify_type(error_notifier, Notifier, allow_none=True)

        return cls(
            *args,
            notifiers=notifiers,
            stop_on_error=stop_on_error,
            stop_on_success=stop_on_success,
            propagate_errors=propagate_errors,
            error_notifier=error_notifier,
            **kwargs
        )

    def __init__(self, notifiers, stop_on_error=False, stop_on_success=False, propagate_errors=True,
                 error_notifier=None):
        notifiers = tuple(notifiers)
        for notifier in notifiers:
            verify_type(notifier, Notifier)

        verify_type(stop_on_error, bool)
        verify_type(stop_on_success, bool)
        verify_type(propagate_errors, bool)
        verify_type(error_notifier, Notifier, allow_none=True)

        super().__init__()

        self._notifiers = notifiers
        self._stop_on_error = stop_on_error
        self._stop_on_success = stop_on_success
        self._propagate_errors = propagate_errors
        self._error_notifier = error_notifier

    @property
    def notifiers(self):
        """The notifiers this composite notifier is composed of."""
        return self._notifiers

    @property
    def stop_on_error(self):
        """Whether an exception for one notifier causes later notifiers to be skipped."""
        return self._stop_on_error

    @property
    def stop_on_success(self):
        """Whether a successful return for one notifier causes later notifiers to be skipped."""
        return self._stop_on_success

    @property
    def propagate_errors(self):
        """
        Whether errors from the component notifiers propagate back to the caller. If stop_on_error
        is not set, remaining notifiers will still be notified before the error propagates, and only
        the first encountered error will propagate.
        """
        return self._ignore_errors

    @property
    def error_notifier(self):
        """
        A secondary notifier to which all errors are sent, regardless of whether propagate_errors is
        set.
        """
        return self._error_notifier

    def __call__(self, *args, **kwargs):
        """
        Send a notification on this notifier's channel.

        :return: None
        """
        first_exc = None
        for notifier in self._notifiers:
            try:
                notifier(*args, **kwargs)
                if self._stop_on_success:
                    break
            except Exception as exc:
                if first_exc is None and self._propagate_errors:
                    first_exc = exc
                if self._error_notifier is not None:
                    # noinspection PyBroadException
                    try:
                        self._error_notifier(
                            args=args,
                            kwargs=kwargs,
                            exc_info=sys.exc_info(),
                            traceback=traceback.format_exc()
                        )
                    except Exception:
                        # noinspection PyBroadException
                        try:
                            # This automatically includes a traceback.
                            log.exception("Error in error notifier:")
                        except Exception:
                            # There is nothing else we can do. We can't reraise it, because either
                            # error propagation is turned off, or we already have an error to
                            # propagate.
                            pass
                if self._stop_on_error:
                    break
        if first_exc is not None:
            raise first_exc
