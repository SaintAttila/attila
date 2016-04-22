"""
attila.abc.transactions
=======================

Interface definition for transactional connections.
"""


from abc import ABCMeta, abstractmethod


from . import connections


__author__ = 'Aaron Hosford'
__all__ = [
    "transactional_connection",
]


# noinspection PyPep8Naming
class transactional_connection(connections.connection, metaclass=ABCMeta):
    """
    The transactional_connection class is an abstract base class for connections that support
    transactions.
    """

    @abstractmethod
    def begin(self):
        """Begin a new transaction, returning the transaction nesting depth."""
        raise NotImplementedError()

    @abstractmethod
    def commit(self):
        """End the current transaction."""
        raise NotImplementedError()

    @abstractmethod
    def rollback(self):
        """Rollback the current transaction."""
        raise NotImplementedError()
