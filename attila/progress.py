"""
Progress tracking and completion estimation.
"""


import datetime
import logging


__author__ = 'Aaron Hosford'
__all__ = [
    'progress',
]


log = logging.getLogger(__name__)


class progress:
    """
    Automatically tracks and logs the progress towards completion of a measurable task of
    predetermined size.

    Example Usage:
        for record in progress(records, time_delta=10, header="Processing records..."):
            ...  # Process the record

    """

    def __init__(self, iterable=None, total_count=None, completed_count=0, started=None,
                 count_delta=None, time_delta=None, header=None, footer=None, level=None):
        assert iterable is not None or total_count is not None

        if total_count is None and iterable is not None:
            total_count = len(iterable)

        if started is None:
            started = datetime.datetime.now()

        if isinstance(time_delta, int):
            time_delta = datetime.timedelta(seconds=time_delta)

        self.iterable = iterable
        self.completed_count = completed_count
        self.total_count = total_count
        self.started = started
        self.last_update_count = 0
        self.last_update_time = None

        self.update_count_delta = count_delta
        self.update_time_delta = time_delta
        self.header = header
        self.footer = footer
        self.log_level = level

    def start(self):
        """
        Indicate that the process has started.

        :return: None
        """
        self.started = datetime.datetime.now()

    def setup_automatic_logging(self, count_delta=None, time_delta=None, header=None, footer=None,
                                level=None):
        """
        Setup the automatic progress logging.

        :param count_delta: The maximum number of completed items between automatic progress
            logging.
        :param time_delta: The maximum time between automatic progress logging, as a
            datetime.timedelta instance.
        :param header: The header when automatically logging progress.
        :param footer: The add_footer when automatically logging progress.
        :param level: The log level when automatically logging progress.
        :return: None
        """

        if count_delta is not None:
            self.update_count_delta = count_delta
        if time_delta is not None:
            if isinstance(time_delta, int):
                time_delta = datetime.timedelta(seconds=time_delta)
            self.update_time_delta = time_delta
        if header is not None:
            self.header = header
        if footer is not None:
            self.footer = footer
        if level is not None:
            self.log_level = level

    def automatic_log_needed(self):
        """
        Determine whether an automatic progress log is needed.

        :return: A bool indicating whether it is time to log the progress.
        """
        return (
            (self.update_count_delta is not None and
             self.completed_count - self.last_update_count >= self.update_count_delta) or
            (self.update_time_delta is not None and
             (datetime.datetime.now() - (self.last_update_time or self.started) >=
              self.update_time_delta))
        )

    def update(self, completed_count=1):
        """
        Update the number of completed items. If automatic logging is setup and a sufficient count
        or time period has passed, log the progress.

        :param completed_count:
        :return: None
        """
        self.completed_count += completed_count
        if self.automatic_log_needed():
            self.log_progress()

    def get_percent_completed(self):
        """
        Return the percent already completed.

        :return: The percentage completed, as a float.
        """

        return self.completed_count / self.total_count * 100

    def get_projected_remaining(self):
        """
        Estimate the remaining time to completion.

        :return: A datetime.timedelta instance.
        """
        seconds_passed = (datetime.datetime.now() - self.started).total_seconds()

        # Add 1 to each term to prevent div by zero and still get a meaningful estimate.
        rate = (seconds_passed + 1) / (self.completed_count + 1)
        remaining_seconds = (self.total_count - self.completed_count + 1) * rate
        return datetime.timedelta(seconds=remaining_seconds)

    def get_projected_completion(self):
        """
        Estimate the completion time.

        :return: A datetime.datetime instance.
        """
        return datetime.datetime.now() + self.get_projected_remaining()

    def log_progress(self, header=None, footer=None, level=None):
        """
        Log the current progress in a standard format.

        :param header: A header line to be included above the progress stats in the log message.
        :param footer: A add_footer line to be included below the progress stats in the log message.
        :param level: The log level at which to log the message.
        :return: None
        """

        if header is None:
            header = self.header
        if footer is None:
            footer = self.footer
        if level is None:
            level = self.log_level
            if level is None:
                level = logging.INFO

        self.last_update_count = self.completed_count
        self.last_update_time = datetime.datetime.now()

        if log.level > level:
            return  # It won't get logged, so skip all the computations.

        if header:
            message = str(header) + "\n"
        else:
            message = ""
        message += "Percent completed: %s%%\n" % round(self.get_percent_completed(), 1)
        message += "Remaining time: %s\n" % self.get_projected_remaining()
        message += "Expected completion: %s" % self.get_projected_completion()
        if footer:
            message += "\n" + str(footer)
        log.log(level, message)

    def __enter__(self):
        if not self.completed_count:
            self.started = datetime.datetime.now()
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False  # Do not suppress errors.

    def __iter__(self):
        assert self.iterable is not None
        self.setup_automatic_logging()
        for item in self.iterable:
            yield item
            self.update()
