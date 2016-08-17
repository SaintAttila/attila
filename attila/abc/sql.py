"""
Interface definition for SQL connections.
"""


from abc import ABCMeta, abstractmethod


import sql_dialects.ast
import sql_dialects.dialects


from . import configurations
from . import connections
from . import rpc

from ..exceptions import OperationNotSupportedError, verify_type


__author__ = 'Aaron Hosford'
__all__ = [
    "RecordSet",
    "sql_connection",
]


class RecordSet(metaclass=ABCMeta):
    """
    A RecordSet is returned whenever a query is executed. It provides an interface to the selected
    data. Each row is yielded as a tuple.
    """

    @abstractmethod
    def _next(self):
        """
        Get the next row in the record set. If no more records are available, raise a StopIteration
        exception.

        :return: The next row in the record set.
        :rtype: An OrderedDict instance.
        """
        raise NotImplementedError()

    def __next__(self):
        return tuple(self._next())

    def __iter__(self):
        while True:
            yield tuple(self._next())


class SQLConnector(connections.Connector, configurations.Configurable, metaclass=ABCMeta):
    """
    Stores the ADODB connection information for a database as a single object which can then be
    passed around instead of using multiple parameters to a function. Use str(connector) to get the
    actual connection string.
    """

    def __init__(self, connection_type, dialect=None):
        verify_type(dialect, str, non_empty=True, allow_none=True)
        assert issubclass(connection_type, sql_connection) and connection_type is not sql_connection

        super().__init__(connection_type)

        self._dialect = dialect

    @property
    def dialect(self):
        """The name of the SQL dialect associated with this connector."""
        return self._dialect


# noinspection PyPep8Naming
class sql_connection(rpc.rpc_connection, metaclass=ABCMeta):
    """
    The sql_connection class is an abstract base class for connections to SQL servers.
    """

    def __init__(self, connector):
        verify_type(connector, SQLConnector)
        super().__init__(connector)

    @abstractmethod
    def _execute(self, script):
        """
        Remotely execute a script.

        :param script: The script to execute.
        :return: The results, or None.
        """
        raise OperationNotSupportedError()

    @abstractmethod
    def _call(self, name, *args, **kwargs):
        """
        Execute a named remote procedure.

        :param name: The name of the remote procedure to execute.
        :param args: Unnamed arguments to be passed to the remote procedure.
        :param kwargs: Named arguments to be passed to the remote procedure.
        :return: The results, or None.
        """
        raise OperationNotSupportedError()

    def execute(self, script):
        """
        Remotely execute a script.

        :param script: The script to execute.
        :return: The results, or None.
        """
        self.verify_open()

        if isinstance(script, sql_dialects.ast.SQLExpression):
            try:
                script = sql_dialects.dialects.get_dialect(self._connector.dialect)
            except KeyError as exc:
                if self._connector.dialect is None:
                    raise KeyError("SQL builder used with no default dialect set.") from exc
                else:
                    raise KeyError("SQL builder used with unsupported dialect: %s" % self._connector.dialect) from exc

        result = self._execute(script)
        assert result is None or isinstance(result, RecordSet)
        return result

    def call(self, name, *args, **kwargs):
        """
        Execute a named remote procedure.

        :param name: The name of the remote procedure to execute.
        :param args: Unnamed arguments to be passed to the remote procedure.
        :param kwargs: Named arguments to be passed to the remote procedure.
        :return: The results, or None.
        """
        self.verify_open()
        result = self._call(name, *args, **kwargs)
        assert result is None or isinstance(result, RecordSet)
        return result
