"""
attila.context
==============

Automation time/activity tracking.

"""


import datetime
import logging

__all__ = [
    'TaskType',
    'Task',
    'Tracker',
    'activity',
]

log = logging.getLogger(__name__)


# TODO: Provide a ScriptContext class that sets up logging, error handling, etc. automatically with a
#       single 'with' statement, and just use the built-in Python logging module's functionality instead
#       of BaseLog. This new class will supplant BaseLoad.


class TaskType:

    def __init__(self, name, savings_per, cost_center_id, time_types, time_thresholds, cutoff, profile,
                 override_savings):
        self.name = name
        self.savings_per = savings_per
        self.cost_center_id = cost_center_id
        self.time_types = time_types
        self.time_thresholds = time_thresholds
        self.cutoff = cutoff
        self.profile = profile
        self.override_savings = override_savings


class Task:

    def __init__(self, tracker, task_type, start_time=None):
        assert isinstance(tracker, Tracker)
        assert isinstance(task_type, TaskType)
        if start_time is None:
            start_time = datetime.datetime.now()
        else:
            assert isinstance(start_time, datetime.datetime)
        self.task_type = task_type
        self.start_time = start_time
        self._finished = False

    def __del__(self):
        if not self._finished:
            self.finish(successful=False)

    def finish(self, successful=True):
        # TODO: Notify the tracker so the task's completion can be documented.
        self._finished = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish(not (exc_type or exc_val or exc_tb))
        return False  # Do not suppress errors


class Tracker:

    # TODO: This should supplant BaseBucket.

    def start(self, task_type):
        # Return a new task of the given type

    def


class activity:
    """
    Use with the 'with' statement to automatically track what activity is being performed. Use logging
    flags to control what events are logged.

    Example Usage:
        with activity("Doing stuff..."):
            print("Now I'm doing stuff.")

            with activity("Doing more detailed stuff..."):
                print("This is getting complicated.")

    If and when an error occurs, the nested tasks that were failed will be automatically logged. Logging
    also takes place automatically when the with block is entered and exited cleanly. The default log
    levels can be set at the class level:

        activity.enter_log_level = logging.DEBUG
        activity.exit_log_level = logging.INFO
        activity.error_log_level = logging.CRITICAL

    This is handy for testing and debugging, when more in-depth logging is needed, since a lot of normally
    unnecessary logging can be turned on/off with a single switch.
    """

    # Defaults for all class instances:
    enter_log_level = logging.INFO
    exit_log_level = logging.DEBUG
    error_log_level = logging.ERROR
    logger = logging.getLogger("activity")

    def __init__(self, description, logger=None, enter_log_level=None, exit_log_level=None,
                 error_log_level=None):
        self.description = str(description)

        # Overrides for this instance, only:
        if enter_log_level is not None:
            self.enter_log_level = enter_log_level
        if exit_log_level is not None:
            self.exit_log_level = exit_log_level
        if error_log_level is not None:
            self.error_log_level = error_log_level
        if log is not None:
            self.logger = logger

    def __enter__(self):
        self.logger.log(self.enter_log_level, 'Started activity: %s', self.description)

    def __exit__(self, cExcType, oExcValue, aTraceback):
        if cExcType or oExcValue or aTraceback:
            self.logger.log(self.error_log_level, 'Failed activity: %s', self.description)
        else:
            self.logger.log(self.exit_log_level, 'Completed activity: %s', self.description)
        return False  # Indicates exceptions should NOT be suppressed.
