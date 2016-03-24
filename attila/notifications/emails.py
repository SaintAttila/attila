import configparser
import datetime


from .. import strings, emails
from ..abc.notifications import Notification, Channel, Notifier
from ..plugins import load_channel_from_config


__all__ = [
    'Email',
    'EmailChannel',
    'EmailNotifier',
]


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
        sender = emails.validate_email_address(sender)
        to = frozenset(strings.to_list_of_strings(to, normalizer=emails.validate_email_address))
        cc = frozenset(strings.to_list_of_strings(cc, normalizer=emails.validate_email_address))
        bcc = frozenset(strings.to_list_of_strings(bcc, normalizer=emails.validate_email_address))

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
        :rtype: attila.notifications.emails.Email
        """
        time_stamp = datetime.datetime.now()
        subject = time_stamp.strftime(self._subject_template.format(*args, **kwargs))
        body = time_stamp.strftime(self._body_template.format(*args, **kwargs))
        if self._footer:
            body += emails.get_standard_footer()
        return Email(subject, body, attachments)


