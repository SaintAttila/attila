"""
attila.adodb
============

ADODB database interface for Python
"""

import configparser
from collections import OrderedDict

import win32com.client

from .abc import connections
from .abc import configuration
from .abc import sql
from .abc import transactions


class Constants:
    """
    Microsoft-defined constants for use with ADODB.
    These have the original names (as ugly as they are) preserved for Googling convenience.
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
    An ADODBRecordSet is returned whenever a query is executed. It provides an interface to the selected data.
    """

    def __init__(self, com_object):
        self._com_object = com_object

    def _next(self):
        if self._com_object.EOF or self._com_object.BOF:
            raise StopIteration()

        # We should never expose the raw COM object at all. Grab the values out and convert them to an ordered
        # dictionary instead. An ordered dictionary is just like an ordinary dict, except that when you iterate
        # over its keys, values, or items, the original order is preserved.
        result = OrderedDict((field.Name, field.Value) for field in self._com_object.Fields)

        self._com_object.MoveNext()
        return result


class ADODBConnector(connections.Connector, configuration.Configurable):
    """
    Stores the ADODB connection information for a database as a single object which can then be passed around instead of
    using multiple parameters to a function. Use str(connector) to get the actual connection string.
    """

    def __init__(self, server=None, database=None, driver=None, credential=None, trusted=None):
        if server is not None:
            assert isinstance(server, str)
            assert server

        if database is not None:
            assert isinstance(database, str)
            assert database

        if driver is not None:
            assert isinstance(driver, str)
            assert driver

        assert not credential or (credential.user and credential.password)

        if trusted is not None:
            assert trusted in (0, 1, False, True)
            trusted = bool(trusted)
            assert not trusted or not credential

        super().__init__(adodb_connection)

        self._server = server
        self._database = database
        self._driver = driver or 'SQL Server'
        self._credential = credential if credential else None
        self._trusted = trusted

    def is_configured(self):
        return self._server is not None and self._database is not None

    def configure(self, config, section):
        assert isinstance(config, configparser.ConfigParser)
        assert section and isinstance(section, str)

        super().configure(config, section)

        config_section = config[section]

        server = config_section['Server']
        database = config_section['Database']
        driver = config_section.get('Driver', self._driver)
        trusted = config.getboolean(section, 'Trusted', fallback=None)

        # This has to be imported here because the security module depends on this module, and we would get an import
        # cycle otherwise.
        import attila.security

        # If no credentials are specified, this will simply return an empty credential.
        credential = attila.security.Credential.load_from_config(config, section)

        assert server
        assert database

        assert not credential or (credential.user and credential.password)

        if trusted is not None:
            assert trusted in (0, 1, False, True)
            trusted = bool(trusted)
            assert not trusted or not credential

        self._server = server
        self._database = database
        self._driver = driver or 'SQL Server'
        self._credential = credential
        self._trusted = trusted

    @property
    def server(self):
        return self._server

    @property
    def database(self):
        return self._database

    @property
    def driver(self):
        return self._driver

    @property
    def credential(self):
        return self._credential

    @property
    def trusted(self):
        return self._trusted

    def connection(self, command_timeout=None, connection_timeout=None, auto_reconnect=True, cursor_location=None):
        return super().connection(command_timeout, connection_timeout, auto_reconnect, cursor_location)

    def __str__(self):
        result = "Driver={%s};Server={%s};Database={%s}" % (self._driver, self._server, self._database)
        if self._credential:
            user, password = self._credential
            result += ";Uid={%s};Pwd={%s}" % (user, password)
        if self._trusted is not None:
            result += ";Trusted_Connection=%s" % repr(self._trusted)
        return result

    def __repr__(self):
        keyword = False
        args = [repr(self._server), repr(self._database)]
        for name, value in (('driver', self._driver), ('credential', self._credential), ('trusted', self._trusted)):
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

    def __init__(self, connector, command_timeout=None, connection_timeout=None, auto_reconnect=True,
                 cursor_location=None):
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

        # The connection timeout is how long we're allowed to take to *establish* a connection.
        if connection_timeout is None:
            self._connection_timeout = 60  # Default is 1 minute
        else:
            self._connection_timeout = connection_timeout

        self._auto_reconnect = bool(auto_reconnect)

        self._cursor_location = cursor_location

    @property
    def is_open(self):
        return self._com_object is not None and bool(self._com_object.State & Constants.adStateOpen)

    def open(self):
        super().open()

        # The state may have other bits set, but we only care about the one that indicates whether it's open or not.
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
        """Close the ADODB connection"""
        return self._com_object.Close()

    def begin(self):
        """Begin a new transaction, returning the transaction nesting depth."""
        self.open()
        return self._com_object.BeginTrans()

    def commit(self):
        """End the current transaction."""
        return self._com_object.CommitTrans()

    def rollback(self):
        """Rollback the current transaction."""
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
        Execute a SQL command or query. If a result table is generated, it is returned as an iterator over the records.
        Otherwise None is returned.

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
        Execute a stored procedure. The stored procedure can dump return data to a results table to be queried later on
        or converted to read depending on how the stored procedure handles its data.

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
