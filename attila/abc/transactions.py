from abc import ABCMeta, abstractmethod

from attila.abc import connections

__author__ = 'Aaron Hosford'


# noinspection PyPep8Naming
class transactional_connection(connections.connection, metaclass=ABCMeta):

    @abstractmethod
    def begin(self):
        """Begin a new transaction, returning the transaction nesting depth."""

    @abstractmethod
    def commit(self):
        """End the current transaction."""

    @abstractmethod
    def rollback(self):
        """Rollback the current transaction."""
