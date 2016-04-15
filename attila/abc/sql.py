"""
attila.abc.sql
==============

Interface definition for SQL connections.
"""


from abc import ABCMeta, abstractmethod

from . import rpc
from ..exceptions import OperationNotSupportedError


__all__ = [
    "RecordSet",
    "sql_connection",
]


class RecordSet(metaclass=ABCMeta):
    """
    A RecordSet is returned whenever a query is executed. It provides an interface to the selected data. Each row is
    yielded as a tuple.
    """

    @abstractmethod
    def _next(self):
        """
        Get the next row in the record set. If no more records are available, raise a StopIteration exception.

        :return: The next row in the record set.
        :rtype: An OrderedDict instance.
        """
        raise NotImplementedError()

    def __next__(self):
        return tuple(self._next())

    def __iter__(self):
        while True:
            yield tuple(self._next())


# noinspection PyPep8Naming
class sql_connection(rpc.rpc_connection, metaclass=ABCMeta):
    """
    The sql_connection class is an abstract base class for connections to SQL servers.
    """

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
