"""
Saint Attila: Python automation in Windows before you can count to five - I mean three.

| And Saint Attila raised the hand grenade up on high, saying, "O LORD, bless this Thy hand grenade that with it Thou
| mayest blow Thine enemies to tiny bits, in Thy mercy."
"""


# Built In
import logging
import os

# 3rd Party
import appdirs


__author__ = 'Aaron Hosford'
__version__ = '0.0'


# def get_parameter_folder(default=None):
#     """
#     The parameter folder is the location where parameters are read.
#     """
#
#     paths = [
#         appdirs.site_config_dir(get_package_name(default='shared'), 'Automation'),
#         appdirs.user_config_dir(get_package_name(default='shared'), 'Automation')
#     ]
#     for path in paths:
#         if os.path.isdir(path):
#             return path
#     return os.getcwd()


def get_log_folder():
    """
    The log folder is the location where logs are written.
    """

    path = appdirs.user_log_dir(get_package_name(default='anonymous'), 'automation')
    if not os.path.isdir(path):
        return path

    return os.getcwd()






class Activity:
    """Use with the 'with' statement to automatically track what activity is
    being performed. Use logging flags to control what events are logged."""

    # Defaults for all class instances:
    enter_log_level = logging.INFO
    exit_log_level = logging.INFO
    exception_log_level = logging.ERROR

    def __init__(self, description, enter_log_level, exit_log_level=None, exception_log_level=None, logger=None):
        assert isinstance(description, str)
        self.description = description
        self.logger = logger or logging.getLogger(get_package_name(default='anonymous'))

        # Overrides for this instance, only:
        if enter_log_level is not None:
            self.enter_log_level = bool(enter_log_level)
        if exit_log_level is not None:
            self.exit_log_level = bool(exit_log_level)
        if exception_log_level is not None:
            self.exception_log_level = bool(exception_log_level)

    def __enter__(self):
        self.logger.log(self.enter_log_level, 'Started activity: %s', self.description)

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type or exc_value or exc_tb:
            self.logger.log(self.exception_log_level, 'Failed activity: %s', self.description)
        else:
            self.logger.log(self.exit_log_level, 'Completed activity: %s', self.description)
        return False  # Indicates exceptions should NOT be suppressed.
