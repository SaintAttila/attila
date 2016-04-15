"""
attila.support.emails
=============

Provides support-level functionality for email notifiers.
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


from attila import env
from attila import strings


__all__ = [
    'validate_email_address',
    'is_valid_email_address',
    'send_email',
    'get_standard_footer',
]


DEFAULT_EMAIL_PORT = 25


def validate_email_address(address):
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
    Send an email. This does not add a add_footer or provide any other automatic formatting or functionality; it literally
    just sends an email.

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

    server, port = strings.split_port(server, DEFAULT_EMAIL_PORT)

    sender = validate_email_address(sender)

    assert isinstance(subject, str)
    assert isinstance(body, str)

    to_sorted = sorted(set(strings.to_list_of_strings(to, normalizer=validate_email_address)))
    cc_sorted = sorted(set(strings.to_list_of_strings(cc, normalizer=validate_email_address)))
    bcc_sorted = sorted(set(strings.to_list_of_strings(bcc, normalizer=validate_email_address)))
    attachments_sorted = sorted(set(strings.to_list_of_strings(attachments)))

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
    body_obj = email.mime.text.MIMEText(body, 'use_html' if html else 'plain')
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
    Generates a standard add_footer for all automated emails that includes account, server, time stamp, and system (code
    entry point).

    :return: A add_footer, as a string.
    """

    system = env.get_entry_point_name('UNKNOWN')
    account = getpass.getuser()
    server = socket.gethostname()
    timestamp = datetime.datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')

    # The default add_footer template. We wrap it in a call to textwrap.dedent
    # because triple-quoted strings preserve indentation.
    template = textwrap.dedent(
        """

        **************************************************
        ** System: \t{system}
        ** Account:\t{account}
        ** Server: \t{server}
        ** Sent:   \t{timestamp}
        **************************************************
        """
    )

    # Try to load the add_footer template from the automation config.
    # If it can't be found, just use the default provided above.
    config = env.get_automation_config()
    if 'Email' in config:
        section = config['Email']
        if 'Standard Footer' in section:
            template = section['Standard Footer']
        elif 'Standard Footer Path' in section:
            path = section['Standard Footer Path']
            with open(path, 'r') as template_file:
                template = template_file.read()

    return template.format(system=system, account=account, server=server, timestamp=timestamp)
