"""
Bindings for sending notifications to Python logger objects.
"""

import ast
import decimal


from sql_dialects import T, V
from sql_dialects.enums import LiteralTypes


from ..abc.configurations import Configurable
from ..abc.notifications import Notifier
from ..abc.sql import SQLConnector, sql_connection
from ..configurations import ConfigManager
from ..exceptions import OperationNotSupportedError, verify_type
from ..plugins import config_loader
from .. import strings


__author__ = 'Aaron Hosford'
__all__ = [
    'SQLNotifier',
]


STANDARD_DATE_FORMAT = '%Y-%m-%d'
STANDARD_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def _string_parser(string):
    try:
        result = ast.literal_eval(string)
        if isinstance(result, str):
            return result
    except (ValueError, SyntaxError):
        pass
    return string


def _null_parser(string):
    string = string.lower()
    assert string in ('', 'null', 'none', 'nil')
    return None


# TODO: Can we do away with this and just use the config manager to load & parse them?
TYPE_PARSER_MAP = {
    LiteralTypes.DATE: strings.parse_date,
    LiteralTypes.DATE_TIME: strings.parse_datetime,
    LiteralTypes.FLOAT: decimal.Decimal,
    LiteralTypes.BOOLEAN: strings.parse_bool,
    LiteralTypes.INTEGER: int,
    LiteralTypes.NULL: _null_parser,
    LiteralTypes.STRING: _string_parser,
}

TYPE_MAP = {
    'bool': LiteralTypes.BOOLEAN,
    'date': LiteralTypes.DATE,
    'date/time': LiteralTypes.DATE_TIME,
    'datetime': LiteralTypes.DATE_TIME,
    'double': LiteralTypes.FLOAT,
    'float': LiteralTypes.FLOAT,
    'int': LiteralTypes.INTEGER,
    'integer': LiteralTypes.INTEGER,
    'none': LiteralTypes.NULL,
    'null': LiteralTypes.NULL,
    'str': LiteralTypes.STRING,
    'string': LiteralTypes.STRING,
}


@config_loader
class SQLNotifier(Notifier, Configurable):
    """
    A SQL notifier passes incoming notifications to a database connection.
    """

    @staticmethod
    def _parse_field_mapping_line(line):
        """
        Parse a field mapping line, having one of the following forms:

            field_type field_name: value_template
            field_type [field_name]: value_template
            nullable field_type field_name: value_template
            nullable field_type [field_name]: value_template

        Return a tuple of the form:

            (nullable, field_type, field_name, value_template)
        """
        assert isinstance(line, str)
        line = line.strip()
        original_line = line
        split_line = line.split()
        if split_line[0].lower() in ('nullable', 'null'):
            line = line[len(split_line[0]):].strip()
            nullable = True
        else:
            nullable = False
        field_type = ''
        field_name = None
        value_template = None
        in_brackets = False
        for char in line:
            if value_template is not None:
                value_template += char
            elif field_name is not None:
                if not in_brackets and char == ':':
                    value_template = ''
                elif in_brackets and char == ']':
                    in_brackets = False
                elif not field_name and char == '[':
                    in_brackets = True
                else:
                    field_name += char
            elif char.isspace():
                field_name = ''
            else:
                field_type += char
        field_type = field_type.strip().lower()
        if field_name:
            field_name = field_name.strip()
        if value_template:
            value_template = value_template.strip()
        assert field_type and field_name and value_template and not in_brackets, \
            "Malformed field mapping entry:\n%r" % original_line.strip()
        assert field_type in TYPE_MAP
        return nullable, field_type, field_name, value_template

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
        verify_type(section, str, non_empty=True)

        if manager.has_option(section, 'Connection'):
            connection = manager.load_option(section, 'Connection')
        else:
            connector = manager.load_option(section, 'Connector')
            verify_type(connector, SQLConnector)
            connection = connector.connect()
        verify_type(connection, sql_connection)

        keep_open = manager.load_option(section, 'Keep Open', 'bool', True)
        retries = manager.load_option(section, 'Retries', int, 0)

        # TODO: Support stored procedures?
        command_type = manager.load_option(section, 'Command Type', str)
        if command_type:
            command_type = command_type.upper()
        else:
            command_type = 'INSERT'
        assert command_type in ('INSERT', 'UPDATE')

        table = manager.load_option(section, 'Table', str)
        verify_type(table, str, non_empty=True)

        field_mapping = manager.load_option(section, 'Field Mapping', str).strip()
        verify_type(field_mapping, str, non_empty=True)

        field_list = [
            cls._parse_field_mapping_line(line)
            for line in field_mapping.splitlines()
            if line.strip()
        ]

        return cls(
            *args,
            connection=connection,
            table=table,
            fields=field_list,
            command_type=command_type,
            keep_open=keep_open,
            retries=retries,
            **kwargs
        )

    def __init__(self, connection, table, fields, command_type=None, keep_open=True, retries=0):
        verify_type(connection, sql_connection)
        verify_type(command_type, str, non_empty=True, allow_none=True)
        verify_type(table, str, non_empty=True)
        verify_type(keep_open, bool)
        verify_type(retries, int)

        if retries < 0:
            raise ValueError(retries)

        if command_type is None:
            command_type = 'INSERT'
        else:
            command_type = command_type.upper()
            assert command_type in ('INSERT', 'UPDATE')

        entries = []
        for nullable, field_type, field_name, value_template in fields:
            verify_type(nullable, bool)
            verify_type(field_type, str, non_empty=True)
            verify_type(field_name, str, non_empty=True)
            verify_type(value_template, str)

            field_type = field_type.lower()
            assert field_type in TYPE_MAP

            entries.append((nullable, field_type, field_name, value_template))

        super().__init__()

        self._connection = connection
        self._table = table
        self._fields = tuple(entries)
        self._command_type = command_type
        self._keep_open = keep_open
        self._retries = retries

    def __del__(self):
        if self._connection.is_open:
            self._connection.close()

    def __call__(self, msg=None, attachments=None, **kwargs):
        """
        Send a notification on this notifier's channel.

        :param attachments: The file attachments, if any, to include in the notification. (Not
            supported.)
        :return: None
        """

        if attachments is not None:
            raise OperationNotSupportedError("File attachments are unsupported.")

        command = T[self._table]
        if self._command_type == 'INSERT':
            command = command.insert()
        else:
            command = command.update()
        for nullable, field_type, field_name, value_template in self._fields:
            value_str = self.interpolate(value_template, (), kwargs)
            if nullable and value_str.lower() in ('', 'none', 'null'):
                value = None
                sql_type = LiteralTypes.NULL
            else:
                sql_type = TYPE_MAP[field_type]
                parser = TYPE_PARSER_MAP[sql_type]
                value = parser(value_str)
            command = command.set(**{field_name: V(value, sql_type)})

        tries = self._retries + 1
        while True:
            tries -= 1
            # noinspection PyBroadException
            try:
                if self._keep_open:
                    if not self._connection.is_open:
                        self._connection.open()

                    # Sometimes the connection gets broken if there has been a long delay, but
                    # it doesn't show up as closed until an exception occurs. If that could be
                    # the case, just reopen the connection and try one more time. If we get
                    # another exception, we can be confident there is some other problem and
                    # we should let the exception pass through to the caller.

                    # noinspection PyBroadException
                    try:
                        self._connection.execute(command)
                    except Exception:
                        if not self._connection.is_open:
                            self._connection.open()
                            self._connection.execute(command)
                        else:
                            raise
                else:
                    with self._connection:
                        self._connection.execute(command)
                break
            except Exception:
                if tries <= 0:
                    raise
