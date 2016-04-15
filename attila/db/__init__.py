"""
attila.db
=========

Database-related functionality
"""


from ..abc.sql import RecordSet, sql_connection
from ..abc.transactions import transactional_connection
from . import adodb
from . import sqlite


__all__ = [
    'RecordSet',
    'sql_connection',
    'transactional_connection',
    'adodb',
    'sqlite',
]
