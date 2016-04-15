import datetime

from distutils.util import strtobool


from ..abc.configurations import Configurable
from ..abc.connections import Connector, connection
from .. import strings, emails
from ..abc.notifications import Notifier
from ..configurations import ConfigLoader
from ..abc.files import Path
from ..exceptions import verify_type


__all__ = [
    'Email',
    'EmailConnector',
    'EmailNotifier',
]


# TODO: Register this as an entry point in the attila.config_loaders group.
def to_email_address_set(value):
    """
    Parse an email address list string.

    :param value: A string containing the email addresses.
    :return: A set of email addresses.
    """
    verify_type(value, str)
    return set(strings.to_list_of_strings(value, normalizer=emails.validate_email_address))


class EmailConnector(Connector, Configurable):
    """
    A channel for sending emails. An email channel keeps track of the server and email addresses, as well as formatting
    options
    """

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param config_loader: A ConfigLoader instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """

        # Email connectors do not support in-line parameter values.
        raise NotImplementedError()

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

        server = config_loader.load_option(section, 'SMTP Server', str)
        port = config_loader.load_option(section, 'Port', int, None)
        sender = config_loader.load_option(section, 'From', emails.validate_email_address)
        to = config_loader.load_option(section, 'To', to_email_address_set, None)
        cc = config_loader.load_option(section, 'CC', to_email_address_set, None)
        bcc = config_loader.load_option(section, 'BCC', to_email_address_set, None)
        html = config_loader.load_option(section, 'HTML Content', strtobool, False)

        if port is not None:
            server += ':' + str(port)

        return cls(*args, server=server, sender=sender, to=to, cc=cc, bcc=bcc, use_html=html, **kwargs)

    def __init__(self, server, sender, to=None, cc=None, bcc=None, use_html=False):
        verify_type(server, str)
        server, port = strings.split_port(server, default=emails.DEFAULT_EMAIL_PORT)

        sender = emails.validate_email_address(sender)

        if to is not None:
            to = frozenset(emails.validate_email_address(address) for address in to)

        if cc is not None:
            cc = frozenset(emails.validate_email_address(address) for address in cc)

        if bcc is not None:
            bcc = frozenset(emails.validate_email_address(address) for address in bcc)

        verify_type(use_html, bool)

        assert isinstance(use_html, bool)

        assert to or cc or bcc

        super().__init__(EmailNotifier)

        self._server = server
        self._port = port
        self._sender = sender
        self._to = to
        self._cc = cc
        self._bcc = bcc
        self._use_html = use_html

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
    def use_html(self):
        """Whether the email body is html, as opposed to plain text."""
        return self._use_html

    def connect(self, subject_template, body_template, footer=True):
        """Create a new new_instance and return it. The new_instance is not automatically opened."""
        return super().connect(subject_template=subject_template, body_template=body_template, add_footer=footer)


class EmailNotifier(connection, Notifier, Configurable):
    """
    An email notifier acts as a template for email notifications, formatting the objects it is given into a standardized
    template and sending the resulting email notification on to a particular destination.
    """

    @classmethod
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param config_loader: A ConfigLoader instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        # Email connectors do not support in-line parameter values.
        raise NotImplementedError()

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

        # First try to load the connector as an option. Then, failing that, try to load this section as a connector.
        connector = config_loader.load_option(section, 'Connector', default=None)
        if connector is None:
            connector = EmailConnector.load_config_section(config_loader, section)

        subject_template = config_loader.load_option(section, 'Subject', str)

        body_template = config_loader.load_option(section, 'Body', str, default=None)
        if body_template is None:
            body_template_path = config_loader.load_option(section, 'Body Path', Path)
            assert isinstance(body_template_path, Path)
            with body_template_path.open() as body_file:
                body_template = body_file.read()

        add_footer = config_loader.load_option(section, 'Add Footer', strtobool, True)

        return cls(
            *args,
            connector=connector,
            subject_template=subject_template,
            body_template=body_template,
            add_footer=add_footer,
            **kwargs
        )

    def __init__(self, connector, subject_template, body_template, add_footer=True):
        verify_type(connector, EmailConnector)
        verify_type(subject_template, str, non_empty=True)
        verify_type(body_template, str, non_empty=True)
        verify_type(add_footer, bool)

        super().__init__(connector)

        self._subject_template = subject_template
        self._body_template = body_template
        self._add_footer = add_footer

        super().open()  # Email notifiers are always open

    def open(self):
        """Open the connection."""
        pass  # Email notifiers are always open

    def close(self):
        """Close the connection."""
        pass  # Email notifiers are always open

    @property
    def subject_template(self):
        """The string template for the email subject."""
        return self._subject_template

    @property
    def body_template(self):
        """The string template for the email body."""
        return self._body_template

    @property
    def add_footer(self):
        """Whether to add a standard footer to the bottom of the email body."""
        return self._add_footer

    def send(self, *args, attachments=None, **kwargs):
        """
        Send an email notification on this channel.

        :param attachments: The attachments for the email.
        :return: None
        """

        self.verify_open()

        time_stamp = datetime.datetime.now()
        subject = time_stamp.strftime(self._subject_template.format(*args, **kwargs))
        body = time_stamp.strftime(self._body_template.format(*args, **kwargs))
        if self._add_footer:
            body += emails.get_standard_footer()

        attachments = frozenset(strings.to_list_of_strings(attachments or ()))

        emails.send_email(
            self._connector.server + ':' + str(self._connector.port),
            self._connector.sender,
            subject,
            body,
            self._connector.to,
            self._connector.cc,
            self._connector.bcc,
            attachments,
            self._connector.use_html
        )
