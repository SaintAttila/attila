"""
attila.notifications
====================

Base classes and null implementations for notification functionality.
"""

from abc import ABCMeta, abstractmethod

import configparser
import datetime
import keyword
import logging
import sys

from . import emails
from . import plugins
from . import strings


def load_channel_from_config(config, section, default=NotImplemented):
    assert isinstance(config, configparser.ConfigParser)
    assert section and isinstance(section, str)
    if section not in config and section in plugins.CHANNELS:
        if default is NotImplemented:  # We use NotImplemented as a sentinel so None can be a legal default value.
            return plugins.CHANNELS[section]
        else:
            return plugins.CHANNELS.get(section, default)
    config_section = config[section]
    channel_type_name = config_section['Channel Type']
    channel_type = plugins.CHANNEL_TYPES[channel_type_name]
    return channel_type.load_from_config(config, section)


def load_notifier_from_config(config, section, default=NotImplemented):
    assert isinstance(config, configparser.ConfigParser)
    assert section and isinstance(section, str)
    if section not in config and section in plugins.NOTIFIERS:
        if default is NotImplemented:  # We use NotImplemented as a sentinel so None can be a legal default value.
            return plugins.NOTIFIERS[section]
        else:
            return plugins.NOTIFIERS.get(section, default)
    config_section = config[section]
    notifier_type_name = config_section['Notifier Type']
    notifier_type = plugins.CHANNEL_TYPES[notifier_type_name]
    return notifier_type.load_from_config(config, section)


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


class RawChannel(Channel, metaclass=ABCMeta):
    pass


class RawNotification(Notification):

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs


class RawNotifier(Notifier):

    def __init__(self, channel):
        assert isinstance(channel, RawChannel)
        super().__init__(channel)

    def build_notification(self, *args, **kwargs):
        """
        Construct a raw notification from the arguments passed to the send() method.
        """
        return RawNotification(*args, **kwargs)


class CallbackChannel(RawChannel):
    """
    A callback channel passes incoming notifications to an arbitrary Python callback. It allows us to wrap Python
    functions in the notification channel interface so we can easily interchange them.
    """

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        config_section = config[section]
        function = config_section['Function']
        assert all(char.isalnum() or char in ('.', '_') for char in function)
        assert not any(keyword.iskeyword(piece) for piece in function.split('.'))
        function = eval(function)
        assert callable(function)
        return cls(function)

    def __init__(self, callback):
        assert callable(callback)
        self._callback = callback

    @property
    def callback(self):
        return self._callback

    def send(self, notification):
        assert isinstance(notification, RawNotification)
        self._callback(*notification.args, **notification.kwargs)


class LogChannel(RawChannel):

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        logger_name = config[section]['Name']
        logger = logging.getLogger(logger_name)
        level = config.getint(section, 'Level', fallback=logging.INFO)
        return cls(logger, level)

    def __init__(self, logger, level=logging.INFO):
        assert isinstance(logger, logging.Logger)
        assert isinstance(level, int)  # Log levels are always integers.
        self._logger = logger
        self._level = level

    @property
    def logger(self):
        return self._logger

    @property
    def level(self):
        return self._level

    def send(self, notification):
        assert isinstance(notification, RawNotification)
        self._logger.log(self._level, *notification.args, **notification.kwargs)


class FileChannel(RawChannel):

    @classmethod
    def load_from_config(cls, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        file = datetime.datetime.now().strftime(config[section]['File'])
        append = config.getboolean(section, 'Append', fallback=True)
        format_string = config[section].get('Format')
        encoding = config[section].get('Encoding', 'utf-8')
        return cls(file, append, format_string, encoding)

    def __init__(self, file, append=True, format_string=None, encoding=None):
        assert isinstance(file, str)
        assert append == bool(append)
        assert format_string is None or isinstance(format_string, str)
        assert encoding is None or isinstance(encoding, str)

        self._file = file
        self._append = bool(append)
        self._format_string = format_string
        self._encoding = encoding

        if file.lower() in ('stdout', 'stderr'):
            assert append
            assert encoding is None
            self._file_obj = getattr(sys, file.lower())
        else:
            self._file_obj = open(file, mode=('a' if append else 'w'), encoding=encoding)

    def send(self, notification):
        assert isinstance(notification, RawNotification)
        if self._format_string is None:
            print(*notification.args, file=self._file_obj, **notification.kwargs)
        else:
            self._file_obj.write(self._format_string.format(*notification.args, **notification.kwargs))

    def close(self):
        self._file_obj.close()


class Email(Notification):
    """
    An email notification. Includes all content of an email, but excludes server and email address information, which
    is provided by the EmailChannel instance the email is sent on.
    """

    def __init__(self, subject, body, attachments=None):
        assert isinstance(subject, str)
        assert isinstance(body, str)
        self._subject = subject
        self._body = body
        self._attachments = frozenset(strings.to_list_of_strings(attachments))

    @property
    def subject(self):
        """The subject of the email."""
        return self._subject

    @property
    def body(self):
        """The body of the email."""
        return self._body

    @property
    def attachments(self):
        """The attachments of the email."""
        return self._attachments


class EmailChannel(Channel):
    """
    A channel for sending emails. An email channel keeps track of the server and email addresses, as well as formatting
    options
    """

    @classmethod
    def load_from_config(cls, config, section):
        """
        Load an email channel from a section in a config file.

        :param config: The loaded config file.
        :param section: The section name in the config file.
        :return: A new email channel.
        """
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        config_section = config[section]
        server = config_section['SMTP Server']
        sender = config_section['From']
        to = config_section['To']
        cc = config_section.get('CC')
        bcc = config_section.get('BCC')
        html = config.getboolean(section, 'HTML Content', fallback=False)
        return cls(server, sender, to, cc, bcc, html)

    def __init__(self, server, sender, to, cc=None, bcc=None, html=False):
        server, port = strings.split_port(server, default=25)
        sender = emails.validate_email(sender)
        to = frozenset(strings.to_list_of_strings(to, normalizer=emails.validate_email))
        cc = frozenset(strings.to_list_of_strings(cc, normalizer=emails.validate_email))
        bcc = frozenset(strings.to_list_of_strings(bcc, normalizer=emails.validate_email))

        assert to or cc or bcc
        assert html == bool(html)

        self._server = server
        self._port = port
        self._sender = sender
        self._to = to
        self._cc = cc
        self._bcc = bcc
        self._html = bool(html)

    @property
    def server(self):
        """The email server's IP."""
        return self._server

    @property
    def port(self):
        """The email server's port."""
        return self._port

    @property
    def sender(self):
        """The email address to send from."""
        return self._sender

    @property
    def to(self):
        """The email addresses to send to."""
        return self._to

    @property
    def cc(self):
        """The email addresses to carbon copy."""
        return self._cc

    @property
    def bcc(self):
        """The email addresses to blind carbon copy."""
        return self._bcc

    @property
    def html(self):
        """Whether the email body is html, as opposed to plain text."""
        return self._html

    def send(self, notification):
        """
        Send an email notification on this channel.

        :param notification: The email notification to be sent on this channel.
        :return: None
        """
        assert isinstance(notification, Email)

        server = self._server + ':' + str(self._port)

        emails.send_email(
            server,
            self._sender,
            notification.subject,
            notification.body,
            self._to,
            self._cc,
            self._bcc,
            notification.attachments,
            self._html
        )


class EmailNotifier(Notifier):
    """
    An email notifier acts as a template for email notifications, formatting the objects it is given into a standardized
    template and sending the resulting email notification on to a particular channel.
    """

    @classmethod
    def load_from_config(cls, config, section):
        """
        Load an email notifier from a section in a config file.

        :param config: The loaded config file.
        :param section: The section name in the config file.
        :return: A new email notifier.
        """
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)
        config_section = config[section]
        channel_name = config_section['Channel']
        channel = load_channel_from_config(config, channel_name)
        subject_template = config_section['Subject']
        if 'Body' in config_section:
            body_template = config_section['Body']
        else:
            body_path = config_section['Body Path']
            with open(body_path, 'r') as body_file:
                body_template = body_file.read()
        footer = config.getboolean(section, 'Footer Stamp', fallback=True)
        return cls(channel, subject_template, body_template, footer)

    def __init__(self, channel, subject_template, body_template, footer=True):
        assert isinstance(channel, EmailChannel)
        assert isinstance(subject_template, str)
        assert isinstance(body_template, str)
        assert footer == bool(footer)

        super().__init__(channel)

        self._subject_template = subject_template
        self._body_template = body_template
        self._footer = bool(footer)

    @property
    def subject_template(self):
        """The string template for the email subject."""
        return self._subject_template

    @property
    def body_template(self):
        """The string template for the email body."""
        return self._body_template

    @property
    def footer(self):
        """Whether to add a standard footer to the bottom of the email body."""
        return self._footer

    def build_notification(self, *args, attachments=None, **kwargs):
        """
        Build an email notification from the arguments provided to send().

        :param attachments: The attachments for the email.
        :return: An email notification.
        :rtype: Email
        """
        time_stamp = datetime.datetime.now()
        subject = time_stamp.strftime(self._subject_template.format(*args, **kwargs))
        body = time_stamp.strftime(self._body_template.format(*args, **kwargs))
        if self._footer:
            body += emails.get_standard_footer()
        return Email(subject, body, attachments)


# Default plugin instances. See http://stackoverflow.com/a/9615473/4683578 for an explanation of how plugins work in the
# general case. These instances will be registered by the entry_points parameter in setup.py. Other, separately
# installable packages can register their own channel types, channels, and notifiers using the entry_points parameter
# from this package's setup.py as an example. They will be available by name during parsing of config files for
# automations built using attila.
NULL_CHANNEL = NullChannel()
NULL_NOTIFIER = NullNotifier()
STDOUT_CHANNEL = FileChannel('stdout')
STDOUT_NOTIFIER = RawNotifier(STDOUT_CHANNEL)
STDERR_CHANNEL = FileChannel('stderr')
STDERR_NOTIFIER = RawNotifier(STDERR_CHANNEL)
