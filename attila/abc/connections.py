"""
Interface definition for connectors and connections.
"""


from abc import ABCMeta, abstractmethod


from ..exceptions import ConnectionOpenError, ConnectionNotOpenError, verify_type


__author__ = 'Aaron Hosford'
__all__ = [
    "Connector",
    "connection",
]


class Connector(metaclass=ABCMeta):
    """
    The Connector class is an abstract base class for new_instance factories. A Connector represents
    a particular collection of resources, often residing on another server.
    """

    def __init__(self, connection_type):
        assert issubclass(connection_type, connection)
        self._connection_type = connection_type

    @property
    def connection_type(self):
        """The class to which connections created by this connector belong."""
        return self._connection_type

    def connect(self, *args, **kwargs):
        """
        Create a newly configured connection and return it. The connection is *not* automatically
        opened.

        :return: A new connection instance.
        """
        return self.connection_type(self, *args, **kwargs)


class connection(metaclass=ABCMeta):
    """
    The connection class is an abstract base class for connection objects. It represents a link to a
    particular collection of resources through which those resource can be accessed.
    """

    def __init__(self, connector):
        verify_type(connector, Connector)
        verify_type(self, connector.connection_type)
        self._connector = connector
        self._is_open = False

    def __del__(self):
        if getattr(self, '_is_open', None):
            self.close()

    @property
    def is_open(self):
        """Whether the new_instance is currently open."""
        return self._is_open

    @abstractmethod
    def open(self):
        """Open the connection."""
        self.verify_closed()
        self._is_open = True

    @abstractmethod
    def close(self):
        """Close the connection."""
        self.verify_open()
        self._is_open = False

    def verify_open(self):
        """
        Raise an exception if the new_instance is not open.
        """
        if not self._is_open:
            raise ConnectionNotOpenError("The new_instance is not currently open.")

    def verify_closed(self):
        """
        Raise an exception if the new_instance is not closed.
        """
        if self._is_open:
            raise ConnectionOpenError("The new_instance is currently open.")

    def __enter__(self):
        self.open()
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False  # Do not suppress exceptions
