from abc import ABCMeta, abstractmethod

__author__ = 'Aaron Hosford'


# TODO: Make the various *Info classes in this package inherit from this, and rename them to *Connector
class Connector(metaclass=ABCMeta):
    """
    The Connector class is an abstract base class for connection factories. A Connector represents a particular
    collection of resources, often residing on another server.
    """

    def __init__(self, connection_type):
        assert issubclass(connection_type, connection)
        self._connection_type = connection_type

    @property
    def connection_type(self):
        """The class to which connections created by this connector belong."""
        return self._connection_type

    @abstractmethod
    def connection(self, *args, **kwargs):
        """Create a new connection and return it."""
        return self._connection_type(self, *args, **kwargs)


# TODO: Make the various *Connection classes in this package inherit from this,and rename them to *_connection
class connection(metaclass=ABCMeta):
    """
    The connection class is an abstract base class for connection objects. It represents a link to a particular
    collection of resources through which those resource can be accessed.
    """

    def __init__(self, connector):
        assert isinstance(connector, Connector)
        assert isinstance(self, connector.connection_type)
        self._connector = connector
        self._is_open = False

    @property
    def connector(self):
        """The connector used to create this connection."""
        return self._connector

    @property
    def is_open(self):
        """Whether the connection is currently open."""
        return self._is_open

    @abstractmethod
    def open(self):
        """Open the connection."""
        assert not self._is_open
        self._is_open = True

    @abstractmethod
    def close(self):
        """Close the connection."""
        assert self._is_open
        self._is_open = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False  # Do not suppress exceptions
