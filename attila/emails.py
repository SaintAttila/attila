"""
attila.emails
=============

Email notification functionality.
"""


import datetime
import email
import email.mime.base
import email.mime.multipart
import email.mime.text
import email.utils
import getpass
import os
import smtplib
import socket
import textwrap


import attila.env
import attila.notifications
import attila.strings


def validate_email(address):
    """
    Validate an email address. If it is malformed, raise an exception.

    :param address: The address to validate.
    :return: The normalized address string.
    """
    address = email.utils.parseaddr(address)[1]  # Ignore preceding name, etc. We just want the address.
    assert address  # Non-empty string
    assert len(address.split()) == 1  # No spaces
    assert address.count('@') == 1  # Exactly 1 @ sign
    user, domain = address.split('@')
    assert user  # Non-empty user
    assert '.' in domain  # At least one . in domain
    assert all(domain.split('.'))  # No . at start or end, and at most one . at a time
    return address


def is_valid_email(address):
    """
    Determine whether an email address is valid.

    :param address: The address to validate.
    :return: Whether the address is valid.
    """
    # noinspection PyBroadException
    try:
        validate_email(address)
    except Exception:
        return False
    else:
        return True


def send_email(server, sender, subject, body, to, cc=None, bcc=None, attachments=None, html=False):
    """
    Send an email. This does not add a footer or provide any other automatic formatting or functionality; it literally
    just sends an email.

    :param server: The email server address.
    :param sender: The email address to appear in the 'from' field.
    :param subject: The subject of the email.
    :param body: The body of the email.
    :param to: The email address(es) to appear in the 'to' field.
    :param cc: The email address(es) to receive carbon copies.
    :param bcc: The email address(es) to receive blind carbon copies.
    :param attachments: The files to attach.
    :param html: Whether the body is html, as opposed to plain text.
    :return: The email object.
    """

    server, port = attila.strings.split_port(server)

    sender = validate_email(sender)

    assert isinstance(subject, str)
    assert isinstance(body, str)

    to_sorted = sorted(set(attila.strings.to_list_of_strings(to, normalizer=validate_email)))
    cc_sorted = sorted(set(attila.strings.to_list_of_strings(cc, normalizer=validate_email)))
    bcc_sorted = sorted(set(attila.strings.to_list_of_strings(bcc, normalizer=validate_email)))
    attachments_sorted = sorted(set(attila.strings.to_list_of_strings(attachments)))

    message = email.mime.multipart.MIMEMultipart()

    # Add attachments
    for attachment in attachments_sorted:
        with open(attachment, 'rb') as attachment_file:
            attachment_data = attachment_file.read()
        attachment_obj = email.mime.base.MIMEBase('application', 'octet-stream')
        attachment_obj.set_payload(attachment_data)
        email.encoders.encode_base64(attachment_obj)
        attachment_obj.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attachment))
        message.attach(attachment_obj)

    # Add body
    body_obj = email.mime.text.MIMEText(body, 'html' if html else 'plain')
    message.attach(body_obj)

    # Add header info
    message['From'] = sender
    message['To'] = ','.join(to_sorted)
    message['CC'] = ','.join(cc_sorted)
    message['Subject'] = subject

    recipients = sorted(set(to_sorted + cc_sorted + bcc_sorted))

    connection = smtplib.SMTP(server, port)
    try:
        connection.sendmail(sender, recipients, message.as_string())
    finally:
        connection.quit()


def get_standard_footer():
    """
    Generates a standard footer for all automated emails that includes account, server, time stamp, and system (code
    entry point).

    :return: A footer, as a string.
    """

    system = attila.env.get_entry_point_name('UNKNOWN')
    account = getpass.getuser()
    server = socket.gethostname()
    timestamp = datetime.datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')

    # TODO: Try to load this from the automation config, and fall back on this.
    template = """

    **************************************************
    ** System: \t{system}
    ** Account:\t{account}
    ** Server: \t{server}
    ** Sent:   \t{timestamp}
    **************************************************
    """

    return textwrap.dedent(template).format(system=system, account=account, server=server, timestamp=timestamp)


class Email:
    """
    An email notification. Includes all content of an email, but excludes server and email address information, which
    is provided by the EmailChannel instance the email is sent on.
    """

    def __init__(self, subject, body, attachments=None):
        assert isinstance(subject, str)
        assert isinstance(body, str)
        self._subject = subject
        self._body = body
        self._attachments = frozenset(attila.strings.to_list_of_strings(attachments))

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


class EmailChannel(attila.notifications.Channel):
    """
    A channel for sending emails. An email channel keeps track of the server and email addresses, as well as formatting
    options
    """

    def __init__(self, server, sender, to, cc=None, bcc=None, html=False):
        server, port = attila.strings.split_port(server, default=25)
        sender = validate_email(sender)
        to = frozenset(attila.strings.to_list_of_strings(to, normalizer=validate_email))
        cc = frozenset(attila.strings.to_list_of_strings(cc, normalizer=validate_email))
        bcc = frozenset(attila.strings.to_list_of_strings(bcc, normalizer=validate_email))

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

        send_email(
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


class EmailNotifier(attila.notifications.Notifier):
    """
    A notifier acts as a template for notifications, formatting the objects it is given into a standardized template
    and sending the resulting notification on to a particular channel.
    """

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
            body += get_standard_footer()
        return Email(subject, body, attachments)
