"""
Utility functions. This module is the "miscellaneous bin", providing a home for simple functions and
classes that don't really belong anywhere else.
"""

import msvcrt
import sys
import time

from .exceptions import TooFewItemsError, TooManyItemsError


__author__ = 'Aaron Hosford'
__all__ = [
    'first',
    'last',
    'only',
    'distinct',
    'wait_for',
    'retry',
    'wait_for_keypress',
    'once',
]


def first(items):
    """
    Return the first item from a sequence. If the item sequence does not contain at least one value,
    raise an exception.

    :param items: The iterable sequence of items.
    :return: The first item in the sequence.
    """
    for item in items:
        return item
    raise TooFewItemsError("No items found in sequence.")


def last(items):
    """
    Return the lst item from a sequence. If the item sequence does not contain at least one value,
    raise an exception.

    :param items: The iterable sequence of items.
    :return: The last item in the sequence.
    """
    result = None
    found = False
    for item in items:
        result = item
        found = True
    if not found:
        raise TooFewItemsError("No items found in sequence.")
    return result


def only(items, ignore_duplicates=False):
    """
    Return the only item from a sequence. If the item sequence does not contain exactly one value,
    raise an exception. Among other scenarios, this is useful for verifying expected results in SQL
    queries when a single row is expected, without bloating the code.

    :param items: The iterable sequence of items.
    :param ignore_duplicates: Whether to ignore multiple occurrences of the same value.
    :return: The only item in the sequence.
    """

    result = None
    found = False
    for item in items:
        if found:
            if not ignore_duplicates or result != item:
                raise TooManyItemsError("Multiple items found in sequence.")
        else:
            found = True
            result = item
    if not found:
        raise TooFewItemsError("No items found in sequence.")
    return result


def distinct(items, key=None):
    """
    Return a list of the items in the same order as they first appear, except that later duplicates
    of the same value are removed. Items in the sequence must be hashable, or, if a key is provided,
    the return values of the key must be hashable.

    :param items: An iterable sequence of items.
    :param key: A function mapping the items to a comparison key.
    :return: A list containing only one of each distinct item.
    """
    assert key is None or callable(key)

    seen = set()
    results = []
    for item in items:
        if key is None:
            key_val = item
        else:
            key_val = key(item)

        if key_val not in seen:
            results.append(item)
            seen.add(key_val)

    return results


def wait_for(condition, timeout=None, attempts=None, interval=None, raise_error=False,
             ignore_errors=True, args=None, kwargs=None):
    """
    Wait for the specified condition to be satisfied.

    :param condition: A callable (function, method, or lambda) which is called repeatedly and
        returns a bool.
    :param timeout: The maximum number of seconds to wait before giving up.
    :param attempts: The maximum number of attempts to make before giving up.
    :param interval: The number of seconds to wait between attempts. Default is 1.
    :param raise_error: Whether to raise a TimeoutError on failure, or just return False.
    :param ignore_errors: Whether to treat errors in the condition as the condition not being met,
        or re-raise them.
    :param args: The argument list to pass to the condition.
    :param kwargs: The keyword arguments to pass to the condition.
    """

    assert callable(condition)
    assert timeout is None or timeout >= 0
    assert attempts is None or attempts >= 0
    assert interval is None or interval >= 0

    if interval is None:
        interval = 1

    args = args or ()
    kwargs = kwargs or {}

    if timeout is None:
        end_time = None
    else:
        end_time = time.time() + timeout

    counter = 0
    while True:
        counter += 1

        # noinspection PyBroadException
        try:
            if condition(*args, **kwargs):
                return True
        except Exception:
            if not ignore_errors:
                raise

        if end_time is not None and time.time() >= end_time:
            if raise_error:
                raise TimeoutError("Timed out after waiting " + str(timeout) + " second(s).")
            else:
                return False

        if attempts is not None and counter >= attempts:
            if raise_error:
                raise TimeoutError("Timed out after making " + str(attempts) + " attempt(s).")
            else:
                return False

        time.sleep(interval)  # Avoid eating unnecessary resources.


def retry(function, timeout=None, attempts=None, interval=None, handler=None,
          args=None, kwargs=None):
    """
    Repeatedly try to call the function until it returns without error. If the function returns
    without error, pass the return value through to the caller. Otherwise, if the maximum time or
    number of attempts is exceeded, pass the most recent exception through to the caller. The
    function is guaranteed to be called at least once.

    :param function: A callable (function, method, or lambda) which is called repeatedly.
    :param timeout: The maximum number of seconds to wait before giving up.
    :param attempts: The maximum number of attempts to make before giving up.
    :param interval: The number of seconds to wait between attempts. Default is 1.
    :param handler: A function that is called after each failed attempt, passing it the
        sys.exc_info() of the exception.
    :param args: The argument list to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    """

    assert callable(function)
    assert handler is None or callable(handler)
    assert timeout is None or timeout >= 0
    assert attempts is None or attempts >= 0
    assert interval is None or interval >= 0

    if interval is None:
        interval = 1

    args = args or ()
    kwargs = kwargs or {}

    if timeout is None:
        end_time = None
    else:
        end_time = time.time() + timeout

    counter = 0
    while True:
        counter += 1

        # noinspection PyBroadException
        try:
            return function(*args, **kwargs)
        except Exception:
            if handler is not None:
                handler(*sys.exc_info())
            if ((end_time is not None and time.time() >= end_time) or
                    (attempts is not None and counter >= attempts)):
                raise

        time.sleep(interval)  # Avoid eating unnecessary resources.


def wait_for_keypress():
    """
    Waits for any keypress, checking every tenth of a second.
    """
    while not msvcrt.kbhit():
        time.sleep(.1)


# noinspection PyPep8Naming
class once:  # Lower-case naming is standard for decorators.
    """
    Function decorator to make a function callable exactly once. Once a function has successfully
    returned without an exception, subsequent calls just return the same return value as the first
    call.

    :param function: The function to be wrapped.
    :return: The wrapped function.
    """

    def __init__(self, function):
        self._function = function
        self._called = False
        self._return_value = None

    def __call__(self, *args, **kwargs):
        if self._called:
            return self._return_value
        self._return_value = self._function(*args, **kwargs)
        self._called = True
