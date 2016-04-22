"""
attila.abc.rpc
==============

Interface definition for remote procedure call server connections.
"""


from abc import ABCMeta, abstractmethod


from . import connections


__author__ = 'Aaron Hosford'
__all__ = [
    "rpc_connection",
]


# noinspection PyPep8Naming
class rpc_connection(connections.connection, metaclass=ABCMeta):
    """
    The rpc_connection class is an abstract base class for connections to remote procedure call
    servers.
    """

    @abstractmethod
    def execute(self, script):
        """
        Remotely execute a script.

        :param script: The script to execute.
        :return: The results, or None.
        """
        self.verify_open()

    @abstractmethod
    def call(self, name, *args, **kwargs):
        """
        Execute a named remote procedure.

        :param name: The name of the remote procedure to execute.
        :param args: Unnamed arguments to be passed to the remote procedure.
        :param kwargs: Named arguments to be passed to the remote procedure.
        :return: The results, or None.
        """
        self.verify_open()
