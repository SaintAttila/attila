"""
attila.adodb
============

ADODB database interface for Python
"""

import configparser


import win32com.client


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


class RecordSet:
    """
    A RecordSet is returned whenever a query is executed. It provides an interface to the selected data.
    """

    def __init__(self, com_object):
        self._com_object = com_object

    def __iter__(self):
        while not (self._com_object.EOF or self._com_object.BOF):
            yield self._com_object.Fields
            self._com_object.MoveNext()

    def _convert(self, to_string):
        if to_string:
            for fields in self:
                yield [('' if field is None else str(field)) for field in fields]
        else:
            for fields in self:
                yield list(fields)

    def convert(self, to_string=True, to_list=True):
        results = self._convert(to_string)
        if to_list:
            return list(results)
        else:
            return results


class SQLConnectionInfo:
    """
    Stores the SQL connection information for a database as a single object which can then be passed around instead of
    using multiple parameters to a function. Use str(connection_info) to get the actual connection string.
    """

    @classmethod
    def load_from_config(cls, config, section):
        """
        Load the SQL connection info from a section in a config file.

        :param config: A configparser.ConfigParser instance.
        :param section: The section to load the connection info from.
        :return: A SQLConnectionInfo instance.
        """

        assert isinstance(config, configparser.ConfigParser)

        config_section = config[section]

        server = config_section['Server']
        database = config_section['Database']
        driver = config_section.get('Driver')
        trusted = config.getboolean(section, 'Trusted', fallback=None)

        # This has to be imported here because the security module depends on this one.
        import attila.security
        credential = attila.security.Credential.load_from_config(config, section)

        return cls(server, database, driver, credential, trusted)

    def __init__(self, server, database, driver=None, credential=None, trusted=None):
        assert isinstance(server, str)
        assert server

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

        self._server = server
        self._database = database
        self._driver = driver or 'SQL Server'
        self._credential = credential if credential else None
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
        args = [self._server, self._database]
        for name, value in (('driver', self._driver), ('credential', self._credential), ('trusted', self._trusted)):
            if value is None or (name == 'driver' and value.lower() == 'sql server'):
                keyword = True
                continue
            if keyword:
                args.append(name + '=' + repr(value))
            else:
                args.append(repr(value))
        return type(self).__name__ + '(' + ', '.join(args) + ')'


class Connection:

    def __init__(self, connection_info, command_timeout=None, connection_timeout=None, auto_reconnect=True,
                 cursor_location=None):
        """
        Create a new Connection instance.

        Example:
            # Get a connection to the database with a command timeout of 100 seconds
            # and a connection timeout of 10 seconds.
            connection = Connection(connection_info, 100, 10)
        """

        assert isinstance(connection_info, (str, SQLConnectionInfo))

        self._com_object = None

        # The command timeout is how long it takes to complete a command.
        if command_timeout is None:
            self._command_timeout = 10 * 60  # Default is 10 minutes
        else:
            self._command_timeout = command_timeout

        # The connection timeout is how long we're allowed to take to *establish* a connection.
        if connection_timeout is None:
            self._connection_timeout = 30  # Default is 30 seconds
        else:
            self._connection_timeout = connection_timeout

        self._connection_info = connection_info

        self._auto_reconnect = bool(auto_reconnect)

        self._cursor_location = cursor_location

        self.open()

    @property
    def connection_info(self):
        return self._connection_info

    @property
    def is_open(self):
        return self._com_object is not None and bool(self._com_object.State & Constants.adStateOpen)

    def open(self):
        # The state may have other bits set, but we only care about the one that indicates whether it's open or not.
        if self._com_object is not None and (self._com_object.State & Constants.adStateOpen):
            return  # If it's open already, do nothing.

        self._com_object = win32com.client.Dispatch("ADODB.Connection")

        # The command timeout is how long it takes to complete a command.
        self._com_object.CommandTimeout = self._command_timeout
        self._com_object.ConnectionTimeout = self._connection_timeout
        if self._cursor_location is not None:
            self._com_object.CursorLocation = self._cursor_location
        self._com_object.Open(str(self._connection_info))

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

    def execute_stored_procedure(self, name, *parameters):
        """
        Execute a stored procedure. The stored procedure can dump return data to a results table to be queried later on
        or converted to read depending on how the stored procedure handles its data.

        Example:
            # Execute a stored procedure with 2 parameters from an open connection.
            connection.execute_stored_procedure(stored_procedure_name, year_str, month_str)

        :param name: The name of the stored procedure to execute.
        :param parameters: Additional parameters to be passed to the stored procedure.
        """

        command = "Exec " + name
        if parameters:
            command += ' ' + ', '.join('@' + str(parameter)for parameter in parameters)

        return self.execute(command)

    def execute(self, command):
        """
        Execute a SQL command or query. If a result table is generated, it is returned as an iterator over the records.
        Otherwise None is returned.

        :param command: The SQL command to execute.
        :return: A RecordSet instance (for queries) or None.
        """
        results = self.execute_raw(command)[0]
        if results:
            return RecordSet(results)
        else:
            return None

    def execute_raw(self, command):
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

    def close(self):
        """Close the ADODB connection"""
        return self._com_object.Close()

    def __enter__(self):
        return self  # The connection is automatically opened when it's created, so there's nothing to do.

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False  # Do not suppress exceptions
