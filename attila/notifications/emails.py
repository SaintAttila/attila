"""
Bindings for sending email notifications.
"""


import datetime

# Yes, these all have to be imported individually.
import email
import email.encoders
import email.mime
import email.mime.base
import email.mime.text
import email.mime.multipart
import email.utils

import getpass
import os
import smtplib
import socket
import textwrap

from distutils.util import strtobool


from ..abc.configurations import Configurable
from ..abc.connections import Connector, connection
from ..abc.files import Path
from ..abc.notifications import Notifier

from ..strings import split_port, to_list_of_strings
from ..configurations import ConfigManager, get_automation_config_manager
from ..context import get_entry_point_name
from ..exceptions import verify_type, OperationNotSupportedError
from ..plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'validate_email_address',
    'is_valid_email_address',
    'send_email',
    'get_standard_footer',
    'to_email_address_set',
    'EmailConnector',
    'EmailNotifier',
]


DEFAULT_EMAIL_PORT = 25


@config_loader('EmailAddress')
def validate_email_address(address):
    """
    Validate an email address. If it is malformed, raise an exception.

    :param address: The address to validate.
    :return: The normalized address string.
    """

    # Ignore preceding name, etc. We just want the address.
    address = email.utils.parseaddr(address)[1]

    assert address  # Non-empty string
    assert len(address.split()) == 1  # No spaces
    assert address.count('@') == 1  # Exactly 1 @ sign

    user, domain = address.split('@')

    assert user  # Non-empty user
    assert '.' in domain  # At least one . in domain
    assert all(domain.split('.'))  # No . at start or end, and at most one . at a time

    return address


def is_valid_email_address(address):
    """
    Determine whether an email address is valid.

    :param address: The address to validate.
    :return: Whether the address is valid.
    """
    # noinspection PyBroadException
    try:
        validate_email_address(address)
    except Exception:
        return False
    else:
        return True


def send_email(server, sender, subject, body, to, cc=None, bcc=None, attachments=None, html=False):
    """
    Send an email. This does not add a add_footer or provide any other automatic formatting or
    functionality; it literally just sends an email.

    :param server: The email server address.
    :param sender: The email address to appear in the 'from' field.
    :param subject: The subject of the email.
    :param body: The body of the email.
    :param to: The email address(es) to appear in the 'to' field.
    :param cc: The email address(es) to receive carbon copies.
    :param bcc: The email address(es) to receive blind carbon copies.
    :param attachments: The files to attach.
    :param html: Whether the body is use_html, as opposed to plain text.
    :return: The email object.
    """

    server, port = split_port(server, DEFAULT_EMAIL_PORT)

    sender = validate_email_address(sender)

    assert isinstance(subject, str)
    assert isinstance(body, str)

    to_sorted = sorted(set(to_list_of_strings(to, normalizer=validate_email_address)))
    cc_sorted = sorted(set(to_list_of_strings(cc, normalizer=validate_email_address)))
    bcc_sorted = sorted(set(to_list_of_strings(bcc, normalizer=validate_email_address)))
    attachments_sorted = sorted(set(to_list_of_strings(attachments)))

    message = email.mime.multipart.MIMEMultipart()

    # Add attachments
    for attachment in attachments_sorted:
        with open(attachment, 'rb') as attachment_file:
            attachment_data = attachment_file.read()
        attachment_obj = email.mime.base.MIMEBase('application', 'octet-stream')
        attachment_obj.set_payload(attachment_data)
        email.encoders.encode_base64(attachment_obj)
        attachment_obj.add_header(
            'Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attachment)
        )
        message.attach(attachment_obj)

    # Add body
    body_obj = email.mime.text.MIMEText(body, 'use_html' if html else 'plain')
    message.attach(body_obj)

    # Add header info
    message['From'] = sender
    message['To'] = ','.join(to_sorted)
    message['CC'] = ','.join(cc_sorted)
    message['Subject'] = subject

    recipients = sorted(set(to_sorted + cc_sorted + bcc_sorted))

    con = smtplib.SMTP(server, port)
    try:
        con.sendmail(sender, recipients, message.as_string())
    finally:
        con.quit()


def get_standard_footer():
    """
    Generates a standard add_footer for all automated emails that includes user, host, time
    stamp, and task (code entry point).

    :return: A add_footer, as a string.
    """

    # The default add_footer template. We wrap it in a call to textwrap.dedent
    # because triple-quoted strings preserve indentation.
    template = textwrap.dedent(
        """

        **************************************************
        ** Task:\t{task}
        ** User:\t{user}
        ** Host:\t{host}
        ** Time:\t{time:%m/%d/%Y %I:%M:%S %p}
        **************************************************
        """
    )

    # Try to load the add_footer template from the automation config.
    # If it can't be found, just use the default provided above.
    config = get_automation_config_manager()
    assert isinstance(config, ConfigManager)
    if config.has_section('Email'):
        if config.has_option('Email', 'Standard Footer'):
            template = config.load_option('Email', 'Standard Footer')
            verify_type(template, str)
        elif config.has_option('Email', 'Standard Footer Path'):
            path = config.load_option('Email', 'Standard Footer Path', Path)
            assert isinstance(path, Path)
            with path.open() as template_file:
                template = template_file.read()

    return template.format(
        task=get_entry_point_name('UNKNOWN'),
        user=getpass.getuser(),
        host=socket.gethostname(),
        time=datetime.datetime.now()
    )


@config_loader('EmailAddressList')
def to_email_address_set(value):
    """
    Parse an email address list string.

    :param value: A string containing the email addresses.
    :return: A set of email addresses.
    """
    verify_type(value, str)
    return set(to_list_of_strings(value, normalizer=validate_email_address))


@config_loader
class EmailConnector(Connector, Configurable):
    """
    A channel for sending emails. An email channel keeps track of the server and email addresses, as
    well as formatting options
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """

        # Email connectors do not support in-line parameter values.
        raise OperationNotSupportedError()

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

        server = manager.load_option(section, 'SMTP Server', str)
        port = manager.load_option(section, 'Port', int, None)
        sender = manager.load_option(section, 'From', validate_email_address)
        to = manager.load_option(section, 'To', to_email_address_set, None)
        cc = manager.load_option(section, 'CC', to_email_address_set, None)
        bcc = manager.load_option(section, 'BCC', to_email_address_set, None)
        html = manager.load_option(section, 'HTML Content', strtobool, False)

        if port is not None:
            server += ':' + str(port)

        return cls(
            *args,
            server=server,
            sender=sender,
            to=to,
            cc=cc,
            bcc=bcc,
            use_html=html,
            **kwargs
        )

    def __init__(self, server, sender, to=None, cc=None, bcc=None, use_html=False):
        verify_type(server, str)
        server, port = split_port(server, default=DEFAULT_EMAIL_PORT)

        sender = validate_email_address(sender)

        if to is not None:
            to = frozenset(validate_email_address(address) for address in to)

        if cc is not None:
            cc = frozenset(validate_email_address(address) for address in cc)

        if bcc is not None:
            bcc = frozenset(validate_email_address(address) for address in bcc)

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
        """The email address to __call__ from."""
        return self._sender

    @property
    def to(self):
        """The email addresses to __call__ to."""
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
        """Create a new connection and return it. The connection is not automatically opened."""
        return super().connect(
            subject_template=subject_template,
            body_template=body_template,
            add_footer=footer
        )


@config_loader
class EmailNotifier(connection, Notifier, Configurable):
    """
    An email notifier acts as a template for email notifications, formatting the objects it is given
    into a standardized template and sending the resulting email notification on to a particular
    destination.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param manager: A ConfigManager instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        # Email connectors do not support in-line parameter values.
        raise OperationNotSupportedError()

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

        # First try to load the connector as an option. Then, failing that, try to load this section
        # as a connector.
        connector = manager.load_option(section, 'Connector', default=None)
        if connector is None:
            connector = EmailConnector.load_config_section(manager, section)

        subject_template = manager.load_option(section, 'Subject', str)

        body_template = manager.load_option(section, 'Body', str, default=None)
        if body_template is None:
            body_template_path = manager.load_option(section, 'Body Path', Path)
            assert isinstance(body_template_path, Path)
            with body_template_path.open() as body_file:
                body_template = body_file.read()

        add_footer = manager.load_option(section, 'Add Footer', strtobool, True)

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

    def __call__(self, *args, attachments=None, **kwargs):
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
            body += get_standard_footer()

        attachments = frozenset(to_list_of_strings(attachments or ()))

        send_email(
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
