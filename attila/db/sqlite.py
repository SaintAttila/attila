"""
SQLite database interface for Python
"""


import sqlite3


from ..abc import configurations
from ..abc import sql
from ..abc import transactions
from ..abc.files import Path

from ..configurations import ConfigManager
from ..exceptions import verify_type, InvalidPathError, OperationNotSupportedError
from ..plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'SQLiteRecordSet',
    'SQLiteConnector',
    'sqlite_connection',
]


class SQLiteRecordSet(sql.RecordSet):
    """
    An SQLiteRecordSet is returned whenever a query is executed. It provides an interface to the
    selected data.
    """

    def __init__(self, cursor):
        self._cursor = cursor

    def _next(self):
        row = self._cursor.fetchone()
        if row is None:
            raise StopIteration()
        return row


@config_loader
class SQLiteConnector(sql.SQLConnector, configurations.Configurable):
    """
    Stores the SQLite connection information for a database as a single object which can then be
    passed around instead of using multiple parameters to a function. Use str(connector) to get the
    actual connection string.
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

        if value == ':memory:':
            path = None
        else:
            path = manager.load_value(value, Path)

        return cls(path)

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

        value = manager.load_option(section, 'Path', str, default=':memory:')
        if value == ':memory:':
            path = None
        else:
            path = manager.load_value(value, Path)

        return cls(path)

    def __init__(self, path=None):
        if path is not None:
            verify_type(path, (str, Path))
            if not isinstance(path, Path):
                path = Path(path)
            if path.is_dir or (not path.is_file and (path.dir is None or not path.dir.is_dir)):
                raise InvalidPathError(str(path))

        super().__init__(sqlite_connection, 'SQLite')

        self._path = path

    @property
    def memory_only(self):
        """Whether the database is only stored in memory, rather than on disk."""
        return self._path is None

    @property
    def path(self):
        """The path to the database."""
        return self._path

    @path.setter
    def path(self, value):
        if value is None or value == ':memory:':
            self._path = None
            return
        verify_type(value, (str, Path))
        if not isinstance(value, Path):
            value = Path(value)
        if value.is_dir or (not value.is_file and (value.dir is None or not value.dir.is_dir)):
            raise InvalidPathError(str(value))
        self._path = value

    def connect(self):
        """Create a new connection and return it. The connection is not automatically opened."""
        return super().connect()

    def __str__(self):
        return ':memory:' if self._path is None else str(self._path)

    def __repr__(self):
        if self._path is None:
            return type(self).__name__ + '()'
        else:
            return type(self).__name__ + '(' + repr(self._path) + ')'


# noinspection PyPep8Naming
class sqlite_connection(sql.sql_connection, transactions.transactional_connection):
    """
    A sqlite_connection manages the state for a connection to a SQLite database, providing an
    interface for executing queries and commands.
    """

    def __init__(self, connector):
        """
        Create a new sqlite_connection instance.

        Example:
            # Get a connection to the database with a command timeout of 100 seconds
            # and a connection timeout of 10 seconds.
            connection = sqlite_connection(connector, 100, 10)
        """

        verify_type(connector, SQLiteConnector)
        super().__init__(connector)

        self._connection = None
        self._cursor = None

    def open(self):
        """Open the connection."""
        self.verify_closed()
        super().open()
        self._connection = sqlite3.connect(str(self._connector))
        self._cursor = self._connection.cursor()

    def close(self):
        """Close the connection."""
        self.verify_open()
        super().close()
        if self._cursor is not None:
            self._cursor.close()
            self._cursor = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def begin(self):
        """Begin a new transaction, returning the transaction nesting depth."""
        self.verify_open()
        self._cursor.begin()

    def commit(self):
        """End the current transaction."""
        self.verify_open()
        self._cursor.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self.verify_open()
        self._cursor.rollback()

    def _execute(self, command):
        """
        Execute a SQL command or query. If a result table is generated, it is returned as an
        iterator over the records. Otherwise None is returned.

        :param command: The SQL command to execute.
        :return: A SQLiteRecordSet instance (for queries) or None.
        """
        self.verify_open()
        self._cursor.execute(command)
        return SQLiteRecordSet(self._cursor)

    def _call(self, name, *parameters):
        """
        Execute a stored procedure. The stored procedure can dump return data to a results table to
        be queried later on or converted to read depending on how the stored procedure handles its
        data.

        Example:
            # Execute a stored procedure with 2 parameters from an open connection.
            connection.call(stored_procedure_name, year_str, month_str)

        :param name: The name of the stored procedure to execute.
        :param parameters: Additional parameters to be passed to the stored procedure.
        """
        raise OperationNotSupportedError('Operation not supported.')
