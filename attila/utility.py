"""
attila.utility
==============

Utility functions.
"""

import sys
import time


def first(items):
    """
    Return the first item from a sequence. If the item sequence does not contain at least one value, raise an exception.

    :param items: The iterable sequence of items.
    :return: The first item in the sequence.
    """
    for item in items:
        return item
    raise ValueError("No items found in sequence.")


def last(items):
    """
    Return the lst item from a sequence. If the item sequence does not contain at least one value, raise an exception.

    :param items: The iterable sequence of items.
    :return: The last item in the sequence.
    """
    result = None
    found = False
    for item in items:
        result = item
        found = True
    if not found:
        raise ValueError("No items found in sequence.")
    return result


def only(items, ignore_duplicates=False):
    """
    Return the only item from a sequence. If the item sequence does not contain exactly one value, raise an exception.
    Among other scenarios, this is useful for verifying expected results in SQL queries when a single row is expected,
    without bloating the code.

    :param items: The iterable sequence of items.
    :param ignore_duplicates: Whether to ignore multiple occurrences of the same value.
    :return: The only item in the sequence.
    """

    result = None
    found = False
    for item in items:
        if found:
            if not ignore_duplicates or result != item:
                raise ValueError("Multiple items found in sequence.")
        else:
            found = True
            result = item
    if not found:
        raise ValueError("No items found in sequence.")
    return result


def distinct(items, key=None):
    """
    Return a list of the items in the same order as they first appear, except that later duplicates of the same value
    are removed. Items in the sequence must be hashable, or, if a key is provided, the return values of the key must be
    hashable.

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


def wait_for(condition, timeout=None, attempts=None, interval=None, raise_error=False, ignore_errors=True,
             args=None, kwargs=None):
    """
    Wait for the specified condition to be satisfied.

    :param condition: A callable (function, method, or lambda) which is called repeatedly.
    :param timeout: The maximum number of seconds to wait before giving up.
    :param attempts: The maximum number of attempts to make before giving up.
    :param interval: The number of seconds to wait between attempts. Default is 1.
    :param raise_error: Whether to raise a TimeoutError on failure, or just return False.
    :param ignore_errors: Whether to treat errors in the condition as the condition not being met, or re-raise them.
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
    Repeatedly try to call the function until it returns without error. If the function returns without error, pass the
    return value through to the caller. Otherwise, if the maximum time or number of attempts is exceeded, pass the most
    recent exception through to the caller. The function is guaranteed to be called at least once.

    :param function: A callable (function, method, or lambda) which is called repeatedly.
    :param timeout: The maximum number of seconds to wait before giving up.
    :param attempts: The maximum number of attempts to make before giving up.
    :param interval: The number of seconds to wait between attempts. Default is 1.
    :param handler: A function that is called after each failed attempt, passing it the sys.exc_info() of the exception.
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
            if (end_time is not None and time.time() >= end_time) or (attempts is not None and counter >= attempts):
                raise

        time.sleep(interval)  # Avoid eating unnecessary resources.
