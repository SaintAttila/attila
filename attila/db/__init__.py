"""
attila.db
=========

Database-related functionality
"""


from . import adodb
from . import sqlite


__all__ = [
    'adodb',
    'sqlite',
]
