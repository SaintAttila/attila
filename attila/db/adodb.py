"""
ADODB database interface for Python
"""


# TODO: Map database to the file system interface. The FS interface already supports row-based
#       reading and writing via the read_rows(), load_rows(), and save_rows() methods. However,
#       those methods expect quotes and delimiters, which aren't required for row-based data stores
#       like SQL tables. Maybe they can simply ignore their delimiter and quote parameters? The
#       question then becomes, what about URLs and SQL queries? There is no doubt that the SQL table
#       and delimited file paradigms can be mapped to each other. But how far do we take it, and
#       how complicated is it going to get?


# TODO: Migrate off of COM, if possible.


import win32com.client


from ..abc import configurations
from ..abc import sql
from ..abc import transactions
from ..configurations import ConfigManager
from ..exceptions import verify_type
from ..plugins import config_loader
from ..security import credentials


__author__ = 'Aaron Hosford'
__all__ = [
    'ADODBRecordSet',
    'ADODBConnector',
    'adodb_connection',
]


ADODB_CONNECTION_COM_CLASS_NAME = "ADODB.Connection"

DEFAULT_DRIVER = 'SQL Server'

# TODO: Add MySQL and other common and supported driver/dialect pairs.
DRIVER_DIALECT_MAP = {
    'sql server': 'T-SQL',
}


class Constants:
    """
    Microsoft-defined constants for use with ADODB. These have the original names (as ugly as they
    are) preserved for Googling convenience. They are not meant to be exported as part of this
    module's public interface and should only be used here within this module.
    """

    # Cursor locations
    adUseNone = 1
    adUseServer = 2  # Default
    adUseClient = 3
    adUseClientBatch = 3

    # Cursor types
    adOpenUnspecified = -1
    adOpenForwardOnly = 0  # Default; does not allow use of transactions. AKA "fire hose mode".
    adOpenKeySet = 1
    adOpenDynamic = 2
    adOpenStatic = 3

    # Object states
    adStateClosed = 0
    adStateOpen = 1
    adStateConnecting = 2
    adStateExecuting = 4
    adStateFetching = 8


class ADODBRecordSet(sql.RecordSet):
    """
    An ADODBRecordSet is returned whenever a query is executed. It provides an interface to the
    selected data.
    """

    def __init__(self, com_object):
        self._com_object = com_object

    def _next(self):
        # It looks dead wrong, but it has to be this way. The COM object's interface is broken.
        if self._com_object.EOF or self._com_object.BOF:
            raise StopIteration()

        # We should never expose the raw COM object at all. Grab the values out and put them in a
        # tuple instead.
        result = tuple(field.Value for field in self._com_object.Fields)

        self._com_object.MoveNext()
        return result


@config_loader
class ADODBConnector(sql.SQLConnector, configurations.Configurable):
    """
    Stores the ADODB connection information for a database as a single object which can then be
    passed around instead of using multiple parameters to a function. Use str(connector) to get the
    actual connection string.
    """

    @staticmethod
    def _tokenize(string_value):
        # TODO: docstring. also, can this be a regex?
        token = ''
        in_braces = False
        for char in string_value:
            if in_braces:
                if char == '}':
                    in_braces = False
                    yield token
                    token = ''
                else:
                    token += char
            elif char == '{':
                if token:
                    yield token
                    token = ''
                in_braces = True
            elif char in ('=', ';'):
                if token:
                    yield token
                    token = ''
                yield char
            else:
                token += char
        assert not in_braces
        if token:
            yield token

    @classmethod
    def _parse(cls, string_value):
        # TODO: docstring
        key = None
        equals = False
        value = None
        results = {}
        for token in cls._tokenize(string_value):
            if token == '=':
                assert key and not equals and value is None
                equals = True
            elif token == ';':
                assert key and equals and value
                key = key.lower()
                assert key not in results
                results[key] = value
                key = None
                equals = False
                value = None
            elif key is None:
                assert not equals and value is None
                key = token
            else:
                assert key and equals and value
                value = token
        if key is not None:
            assert key and equals and value
            key = key.lower()
            assert key not in results
            results[key] = value
        return results

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

        parameter_map = cls._parse(value)

        # We specifically disallow passwords to be stored. It's a major security risk.
        assert 'password' not in parameter_map and 'pwd' not in parameter_map

        # We also want to catch any other, unfamiliar terms.
        for key in parameter_map:
            if key not in {'server', 'database', 'driver', 'trusted_connection', 'uid', 'dialect'}:
                raise KeyError("Unrecognized term: " + repr(key))

        server = parameter_map['server']
        database = parameter_map['database']
        driver = parameter_map.get('driver')
        trusted = parameter_map.get('trusted_connection')
        dialect = parameter_map.get('dialect')

        if trusted is not None:
            trusted = trusted.lower()
            assert trusted in ('true', 'false')
            trusted = (trusted == 'true')

        if trusted:
            credential = None
        else:
            user = parameter_map.get('uid')
            if user is not None:
                credential_string = user + '@' + server + '/adodb'
                credential = \
                    manager.load_value(credential_string, credentials.Credential)
            else:
                credential = None

        return cls(
            *args,
            server=server,
            database=database,
            driver=driver,
            credential=credential,
            trusted=trusted,
            dialect=dialect,
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

        verify_type(section, str, non_empty=True)

        server = manager.load_option(section, 'server', str)
        database = manager.load_option(section, 'database', str)
        driver = manager.load_option(section, 'driver', str, default=None)
        trusted = manager.load_option(section, 'trusted', 'bool', default=None)
        dialect = manager.load_option(section, 'dialect', str, default=None)

        if trusted:
            credential = None
        else:
            credential = manager.load_option(section, 'credential',
                                             credentials.Credential,
                                             default=None)
            if credential is None:
                credential = manager.load_section(section,
                                                  loader=credentials.Credential,
                                                  default=None)

        return cls(
            *args,
            server=server,
            database=database,
            driver=driver,
            credential=credential,
            trusted=trusted,
            dialect=dialect,
            **kwargs
        )

    def __init__(self, server, database, driver=None, credential=None, trusted=None, dialect=None):
        verify_type(server, str, non_empty=True)
        verify_type(database, str, non_empty=True)
        verify_type(dialect, str, non_empty=True, allow_none=True)

        if driver is None:
            driver = DEFAULT_DRIVER
        verify_type(driver, str, non_empty=True)

        if credential and not (credential.user and credential.password):
            raise ValueError("Partially defined credential.")

        if trusted is not None:
            verify_type(trusted, bool)
            if trusted and credential:
                raise ValueError("Connection cannot both be trusted and use credentials.")

        if not dialect and driver.lower() in DRIVER_DIALECT_MAP:
            dialect = DRIVER_DIALECT_MAP[driver.lower()]

        super().__init__(adodb_connection, dialect)

        self._server = server
        self._database = database
        self._driver = driver
        self._credential = credential if credential else None
        self._trusted = trusted

    @property
    def server(self):
        """The DNS name or IP of the server being accessed."""
        return self._server

    @property
    def database(self):
        """The name of the database being accessed."""
        return self._database

    @property
    def driver(self):
        """The name of the driver used to connect to the server."""
        return self._driver

    @property
    def credential(self):
        """The credential object used to connect to the server."""
        return self._credential

    @property
    def trusted(self):
        """Whether the connection is "trusted"."""
        return self._trusted

    def connect(self, command_timeout=None, connection_timeout=None, auto_reconnect=True,
                cursor_location=None):
        """
        Create a new connection and return it. The connection is not automatically opened.

        :param command_timeout: The number of seconds to wait for a command to execute.
        :param connection_timeout: The number of seconds to wait for a connection attempt to
            succeed.
        :param auto_reconnect: Whether to automatically reconnect if the connection is broken.
        :param cursor_location: The initial cursor location.
        :return: The new, unopened connection.
        """
        return super().connect(
            command_timeout=command_timeout,
            connection_timeout=connection_timeout,
            auto_reconnect=auto_reconnect,
            cursor_location=cursor_location
        )

    def __str__(self):
        result = \
            "Driver={%s};Server={%s};Database={%s}" % (self._driver, self._server, self._database)
        if self._credential:
            user, password = self._credential[:2]
            result += ";Uid={%s};Pwd={%s}" % (user, password)
        if self._trusted is not None:
            result += ";Trusted_Connection=%s" % repr(self._trusted)
        if self.dialect is not None:
            result += ";Dialect={%s}" % self.dialect
        return result

    def __repr__(self):
        keyword = False
        args = [repr(self._server), repr(self._database)]
        for name, value in (('driver', self._driver),
                            ('credential', self._credential),
                            ('trusted', self._trusted),
                            ('dialect', self.dialect)):
            if value is None or (name == 'driver' and value.lower() == 'sql server'):
                keyword = True
                continue
            if keyword:
                args.append(name + '=' + repr(value))
            else:
                args.append(repr(value))
        return type(self).__name__ + '(' + ', '.join(args) + ')'


# noinspection PyPep8Naming
@config_loader
class adodb_connection(sql.sql_connection, transactions.transactional_connection,
                       configurations.Configurable):
    """
    An adodb_connection manages the state for a connection to a SQL server via ADODB, providing an
    interface for executing queries and commands.
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
        verify_type(value, str)
        connector = manager.load_value(value, ADODBConnector)
        return cls(*args, connector=connector, **kwargs)

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

        if manager.has_option(section, 'Connector'):
            connector = manager.load_option(section, 'Connector', ADODBConnector)
        else:
            connector = manager.load_section(section, ADODBConnector)
        return cls(*args, connector=connector, **kwargs)

    def __init__(self, connector, command_timeout=None, connection_timeout=None,
                 auto_reconnect=True, cursor_location=None):
        """
        Create a new adodb_connection instance.

        Example:
            # Get a connection to the database with a command timeout of 100 seconds
            # and a connection timeout of 10 seconds.
            connection = adodb_connection(connector, 100, 10)
        """

        assert isinstance(connector, ADODBConnector)

        super().__init__(connector)

        self._com_object = None

        # The command timeout is how long it takes to complete a command.
        if command_timeout is None:
            self._command_timeout = 60 * 60  # Default is 1 hour
        else:
            self._command_timeout = command_timeout

        # The new_instance timeout is how long we're allowed to take to *establish* a new_instance.
        if connection_timeout is None:
            self._connection_timeout = 60  # Default is 1 minute
        else:
            self._connection_timeout = connection_timeout

        self._auto_reconnect = bool(auto_reconnect)

        self._cursor_location = cursor_location

    @property
    def is_open(self):
        """Whether the connection is currently open."""
        return self._com_object is not None and bool(self._com_object.State & Constants.adStateOpen)

    def open(self):
        """Open the ADODB connection."""
        super().open()

        # The state may have other bits set, but we only care about the one that indicates whether
        # it's open or not.
        if self._com_object is not None and (self._com_object.State & Constants.adStateOpen):
            return  # If it's open already, do nothing.

        self._com_object = win32com.client.Dispatch(ADODB_CONNECTION_COM_CLASS_NAME)

        # The command timeout is how long it takes to complete a command.
        self._com_object.CommandTimeout = self._command_timeout
        self._com_object.ConnectionTimeout = self._connection_timeout
        if self._cursor_location is not None:
            self._com_object.CursorLocation = self._cursor_location
        self._com_object.Open(str(self._connector))

    def close(self):
        """Close the ADODB connection"""
        if self.is_open:
            return self._com_object.Close()
        super().close()

    def begin(self):
        """Begin a new transaction, returning the transaction nesting depth."""
        assert self.is_open
        return self._com_object.BeginTrans()

    def commit(self):
        """End the current transaction."""
        assert self.is_open
        return self._com_object.CommitTrans()

    def rollback(self):
        """Rollback the current transaction."""
        assert self.is_open
        return self._com_object.RollbackTrans()

    def _execute_raw(self, command):
        """
        Execute a SQL command or query. The results of the underlying ADODB call are returned as-is.

        :param command: The SQL command to execute.
        :return: A cursor COM object (for queries) or None.
        """
        if self._auto_reconnect:
            if not self.is_open:
                self.open()
            try:
                return self._com_object.Execute(command)
            except:
                try:
                    self._com_object.Close()
                finally:
                    self._com_object = None
                raise
        else:
            return self._com_object.Execute(command)

    def _execute(self, command):
        """
        Execute a SQL command or query. If a result table is generated, it is returned as an
        iterator over the records. Otherwise None is returned.

        :param command: The SQL command to execute.
        :return: A ADODBRecordSet instance (for queries) or None.
        """
        results = self._execute_raw(command)[0]
        if results is None:
            return results
        else:
            return ADODBRecordSet(results)

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

        command = "Exec " + name
        if parameters:
            command += ' ' + ', '.join('@' + str(parameter) for parameter in parameters)

        return self._execute(command)
