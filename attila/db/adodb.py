"""
attila.db.adodb
===============

ADODB database interface for Python
"""


import win32com.client


from ..abc import connections
from ..abc import configurations
from ..abc import sql
from ..abc import transactions

from ..configurations import ConfigLoader
from ..exceptions import verify_type
from ..security import credentials


__all__ = [
    'ADODBRecordSet',
    'ADODBConnector',
    'adodb_connection',
]


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
        if self._com_object.EOF or self._com_object.BOF:
            raise StopIteration()

        # We should never expose the raw COM object at all. Grab the values out and put them in a
        # tuple instead.
        result = tuple(field.Value for field in self._com_object.Fields)

        self._com_object.MoveNext()
        return result


class ADODBConnector(connections.Connector, configurations.Configurable):
    """
    Stores the ADODB new_instance information for a database as a single object which can then be
    passed around instead of using multiple parameters to a function. Use str(connector) to get the
    actual new_instance string.
    """

    @staticmethod
    def _tokenize(string_value):
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
    def load_config_value(cls, config_loader, value, *args, **kwargs):
        """
        Load a class instance from the value of a config option.

        :param config_loader: A ConfigLoader instance.
        :param value: The string value of the option.
        :return: A new instance of this class.
        """
        verify_type(config_loader, ConfigLoader)
        assert isinstance(config_loader, ConfigLoader)

        verify_type(value, str, non_empty=True)

        parameter_map = cls._parse(value)

        # We specifically disallow passwords to be stored. It's a major security risk.
        assert 'password' not in parameter_map and 'pwd' not in parameter_map

        # We also want to catch any other, unfamiliar terms.
        for key in parameter_map:
            if key not in {'server', 'database', 'driver', 'trusted_connection', 'uid'}:
                raise KeyError("Unrecognized term: " + repr(key))

        server = parameter_map['server']
        database = parameter_map['database']
        driver = parameter_map.get('driver')
        trusted = parameter_map.get('trusted_connection')
        user = parameter_map.get('uid')

        if trusted is not None:
            trusted = trusted.lower()
            assert trusted in ('true', 'false')
            trusted = (trusted == 'true')

        if user is not None:
            credential_string = user + '@' + server + '/adodb'
            credential = config_loader.load_value(credential_string, credentials.Credential)
        else:
            credential = None

        return cls(
            *args,
            server=server,
            database=database,
            driver=driver,
            credential=credential,
            trusted=trusted,
            **kwargs
        )

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

        server = config_loader.load_option(section, 'Server', str)
        database = config_loader.load_option(section, 'Database', str)
        driver = config_loader.load_option(section, 'Driver', str, default=None)
        trusted = config_loader.load_option(section, 'Trusted', str, default=None)

        credential = config_loader.load_option(section, 'Credential', credentials.Credential,
                                               default=None)
        if credential is None:
            credential = config_loader.load_section(section, loader=credentials.Credential,
                                                    default=None)

        return cls(
            *args,
            server=server,
            database=database,
            driver=driver,
            credential=credential,
            trusted=trusted,
            **kwargs
        )

    def __init__(self, server, database, driver=None, credential=None, trusted=None):
        verify_type(server, str, non_empty=True)
        verify_type(database, str, non_empty=True)

        if driver is not None:
            verify_type(driver, str, non_empty=True)

        if credential and not (credential.user and credential.password):
            raise ValueError("Partially defined credential.")

        if trusted is not None:
            verify_type(trusted, bool)
            if trusted and credential:
                raise ValueError("Connection cannot both be trusted and use credentials.")

        super().__init__(adodb_connection)

        self._server = server
        self._database = database
        self._driver = driver or 'SQL Server'
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
        """Whether the new_instance is "trusted"."""
        return self._trusted

    def connect(self, command_timeout=None, connection_timeout=None, auto_reconnect=True,
                cursor_location=None):
        """
        Create a new new_instance and return it. The new_instance is not automatically opened.

        :param command_timeout: The number of seconds to wait for a command to execute.
        :param connection_timeout: The number of seconds to wait for a new_instance attempt to
            succeed.
        :param auto_reconnect: Whether to automatically reconnect if the new_instance is broken.
        :param cursor_location: The initial cursor location.
        :return: The new, unopened new_instance.
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
            user, password = self._credential
            result += ";Uid={%s};Pwd={%s}" % (user, password)
        if self._trusted is not None:
            result += ";Trusted_Connection=%s" % repr(self._trusted)
        return result

    def __repr__(self):
        keyword = False
        args = [repr(self._server), repr(self._database)]
        for name, value in (('driver', self._driver),
                            ('credential', self._credential),
                            ('trusted', self._trusted)):
            if value is None or (name == 'driver' and value.lower() == 'sql server'):
                keyword = True
                continue
            if keyword:
                args.append(name + '=' + repr(value))
            else:
                args.append(repr(value))
        return type(self).__name__ + '(' + ', '.join(args) + ')'


# noinspection PyPep8Naming
class adodb_connection(sql.sql_connection, transactions.transactional_connection):
    """
    An adodb_connection manages the state for a new_instance to a SQL server via ADODB, providing an
    interface for executing queries and commands.
    """

    def __init__(self, connector, command_timeout=None, connection_timeout=None,
                 auto_reconnect=True, cursor_location=None):
        """
        Create a new adodb_connection instance.

        Example:
            # Get a new_instance to the database with a command timeout of 100 seconds
            # and a new_instance timeout of 10 seconds.
            new_instance = adodb_connection(connector, 100, 10)
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
        """Whether the new_instance is currently open."""
        return self._com_object is not None and bool(self._com_object.State & Constants.adStateOpen)

    def open(self):
        """Open the ADODB new_instance."""
        super().open()

        # The state may have other bits set, but we only care about the one that indicates whether
        # it's open or not.
        if self._com_object is not None and (self._com_object.State & Constants.adStateOpen):
            return  # If it's open already, do nothing.

        self._com_object = win32com.client.Dispatch("ADODB.adodb_connection")

        # The command timeout is how long it takes to complete a command.
        self._com_object.CommandTimeout = self._command_timeout
        self._com_object.ConnectionTimeout = self._connection_timeout
        if self._cursor_location is not None:
            self._com_object.CursorLocation = self._cursor_location
        self._com_object.Open(str(self._connector))

    def close(self):
        """Close the ADODB new_instance"""
        return self._com_object.Close()

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
        if results:
            return ADODBRecordSet(results)
        else:
            return None

    def _call(self, name, *parameters):
        """
        Execute a stored procedure. The stored procedure can dump return data to a results table to
        be queried later on or converted to read depending on how the stored procedure handles its
        data.

        Example:
            # Execute a stored procedure with 2 parameters from an open new_instance.
            new_instance.call(stored_procedure_name, year_str, month_str)

        :param name: The name of the stored procedure to execute.
        :param parameters: Additional parameters to be passed to the stored procedure.
        """

        command = "Exec " + name
        if parameters:
            command += ' ' + ', '.join('@' + str(parameter) for parameter in parameters)

        return self._execute(command)
