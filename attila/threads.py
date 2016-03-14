"""
attila.threads
==============

Classes and functions for multi-threaded environments and inter-thread/process synchronization and communication.
"""

import ctypes
import sys
import threading
import time
import traceback

import pythoncom

from ctypes import wintypes


# This determines what gets imported by "from <module> import *" statements.
__all__ = [
    "Mutex",
    "Semaphore",
    "AsyncCall",
    "async",
]


# See http://code.activestate.com/recipes/577794-win32-named-mutex-class-for-system-wide-mutex/
class Mutex:
    """Mutex is short for "mutual exclusion". A mutex is an inter-process lock
    which only one running process can own at a time. To use a mutex, first
    create it. This does not lock the mutex; it simply creates an object to
    represent it. Calling the lock method will wait until the mutex becomes
    unlocked by other processes and threads and then lock it by this process.
    Only this thread will be able to unlock it, by calling unlock (or when the
    process ends if it fails to call unlock). Mutexes can also be used with the
    'with' syntax to automatically manage locking scope. This class's locking is
    re-entrant, meaning that as long as you are using the same instance of this
    class, you can lock the mutex multiple times without releasing it in
    between. (You have to call unlock one for each time you called lock.)

    Mutexes serve to protect shared resources from race conditions in a
    multi-threaded environment. For example, suppose you must restrict access
    to a program that is accessed through a COM interface; only one instance
    of this COM-interfaced program can be running at any given time, and only
    one script can safely access it at a time. This can be safely managed by
    designating a single name to represent the shared COM-interfaced program in
    all your scripts, and using mutexes to guard the program. In each script
    that accesses the program, you would create a mutex object and lock it
    before accessing the program, unlocking it again only after the script is
    done with its interactions with the program. The mutex lock request in each
    script will guarantee that the script stops and waits for any other script
    that is already using the shared program to finish what it is doing before
    the newcomer starts to use it. (The hall pass in high school and the
    bathroom key at a gas station are examples of a real-world mutexes.)"""

    # ctypes wrapper for windows function CreateMutexA
    _create = ctypes.windll.kernel32.CreateMutexA
    _create.restype = wintypes.HANDLE
    _create.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCSTR]

    # ctypes wrapper for windows function ReleaseMutex
    _release = ctypes.windll.kernel32.ReleaseMutex
    _release.restype = wintypes.BOOL
    _release.argtypes = [wintypes.HANDLE]

    # ctypes wrapper for windows function CloseHandle
    _close = ctypes.windll.kernel32.CloseHandle
    _close.restype = wintypes.BOOL
    _close.argtypes = [wintypes.HANDLE]

    # ctypes wrapper for windows function WaitForSingleObject
    _wait_for = ctypes.windll.kernel32.WaitForSingleObject
    _wait_for.restype = wintypes.BOOL
    _wait_for.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    MUTEX_TIMED_OUT = 0x102
    MUTEX_RELEASED_NORMALLY = 0
    MUTEX_RELEASED_DUE_TO_PROGRAM_EXIT = 0x80

    def __init__(self, name):
        self._name = name
        self._handle = self._create(None, False, wintypes.LPCSTR(self._name.encode()))
        if not self._handle:
            raise RuntimeError("Failed to create mutex handle for " + repr(self._name) + ".")
        self._held_count = 0

    def __del__(self):
        """Called when no more Python references to the mutex instance exist."""
        if self._handle and not self._close(self._handle):
            raise RuntimeError("Failed to close mutex handle for " + repr(self._name) + ".")
        self._handle = None

    @property
    def name(self):
        """The name of the mutex."""
        return self._name

    @property
    def held_count(self):
        """The number of locks to the mutex currently held by this instance."""
        return self._held_count

    def lock(self, timeout=None):
        """
        Called to lock the mutex. If timeout is provided, the method will return back True or False to indicate whether
        the lock was acquired within the indicated time limit. Otherwise, the method will wait indefinitely until
        successful, which will always return True. An exception will be raised if the lock cannot be acquired for
        reasons other than a request timeout, where False is returned.

        :param timeout: The maximum time, in seconds, to wait for the lock.
        :return: Whether the lock was acquired.
        """
        if self._held_count:
            self._held_count += 1
            return True

        if timeout is None:
            # max int, never time out.
            timeout_milliseconds = 0xFFFFFFFF
        else:
            # approximate max int, take minimum between the two
            timeout_milliseconds = max(min(0xFFFFFFFE, timeout * 1000), 1)

        # Return Values:
        #   0x102 indicates the request timed out
        #   0 indicates the lock was already available or the other program released the handle by calling ReleaseMutex
        #   0x80 indicates the other program released the handle when it exited
        #   Any other value indicates an error handling the request in Windows itself
        status = self._wait_for(self._handle, timeout_milliseconds)

        if status == self.MUTEX_TIMED_OUT:
            # Request timed out
            return False
        elif status in (self.MUTEX_RELEASED_NORMALLY, self.MUTEX_RELEASED_DUE_TO_PROGRAM_EXIT):
            # Mutex was acquired
            self._held_count += 1
            return True
        else:
            # Something went wrong
            raise RuntimeError("Failed to lock mutex " + repr(self._name) + ". Status: " + str(status))

    def unlock(self):
        """Called to unlock the mutex. This should be called once for each time
        that lock is previously called, after the shared resource is no longer
        required."""
        if self._held_count <= 0:
            self._held_count = 0  # Just in case it somehow ended up negative.
            raise ValueError("Mutex " + repr(self._name) + " cannot be released because it is not held.")
        elif self._held_count > 1:
            self._held_count -= 1
        else:
            if not self._release(self._handle):
                raise RuntimeError("Failed to unlock mutex " + repr(self._name) + ".")
            self._held_count = 0

    def __enter__(self):
        """This is called when you use a mutex in a 'with' block, as the block
        is entered."""
        self.lock()
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        """This is called when you use a mutex in a 'with' block, as the block
        is exited."""
        self.unlock()
        return False  # Indicates that errors should NOT be suppressed.


class Semaphore:
    """A semaphore is an inter-process lock which up to N running processes can
    own at a time. It is similar to a mutex, except that there
    are multiple, indistinguishable resources being guarded rather than just
    one. To use a semaphore, first create it. This does not lock the semaphore;
    it simply creates an object to represent it. Calling the lock method will
    wait until one of the N locks of the semaphore becomes unlocked by another
    process or thread, and then lock it by this process. Only this thread will
    be able to unlock it, by calling unlock (or when the process ends if it
    fails to call unlock). Semaphores can also be used with the 'with' syntax
    to automatically manage locking scope. This class's locking is re-entrant,
    meaning that as long as you are using the same instance of this class, you
    can lock the semaphore multiple times without releasing it in between, and
    it will only count as one lock. (You have to call unlock once for each time
    you called lock.)"""

    def __init__(self, name, max_count):
        self._name = name
        self._max_count = max_count
        self._mutexes = []
        self._held_mutex = None

    def __del__(self):
        """Called when no more Python references to the semaphore instance exist."""
        if self._held_mutex:
            while self._held_mutex.held_count > 0:
                self._held_mutex.unlock()
        self._held_mutex = None

    @property
    def name(self):
        """The name of the semaphore."""
        return self._name

    @property
    def held_count(self):
        """The number of re-entrant locks to the same resource currently held by this instance."""
        return 0 if self._held_mutex is None else self._held_mutex.held_count

    @property
    def max_count(self):
        """The number of resources guarded by this semaphore."""
        return self._max_count

    def _poll_and_lock(self):
        """Runs through each of the indexed mutexes to find one that can be locked.
        Returns a Boolean indicating whether a mutex was successfully acquired."""
        if self._held_mutex:
            return self._held_mutex.lock(0)

        for index in range(self._max_count):
            if index >= len(self._mutexes):
                mutex = Mutex(self._name + '/' + str(index))
                self._mutexes.append(mutex)
            else:
                mutex = self._mutexes[index]

            if mutex.lock(0):
                self._held_mutex = mutex
                return True

        return False

    def lock(self, timeout=None, interval=.1):
        """
        Called to lock the semaphore. If timeout is provided, the method will return back True or False to indicate
        whether a lock was acquired within the indicated time limit. Otherwise, the method will wait indefinitely and
        will always return True once complete. An exception will be raised if the lock cannot be acquired for reasons
        other than a request timeout.

        :param timeout: The maximum time in seconds to wait for the lock.
        :param interval: The time in seconds between polls.
        :return: Whether the lock was acquired.
        """
        if timeout is None:
            end_time = None
        else:
            end_time = time.time() + timeout

        while True:
            if self._poll_and_lock():
                return True

            if end_time is not None and time.time() >= end_time:
                return False

            time.sleep(interval)

    def unlock(self):
        """Called to unlock the semaphore. This should be called once for each time
        that lock is previously called, after the shared resources are no longer
        required."""
        if self._held_mutex is None:
            raise ValueError("Semaphore lock for " + repr(self._name) + " cannot be released because it is not held.")

        self._held_mutex.unlock()

        if self._held_mutex.held_count <= 0:
            self._held_mutex = None

    def __enter__(self):
        """This is called when you use a semaphore in a 'with' block, as the block
        is entered."""
        self.lock()
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        """This is called when you use a semaphore in a 'with' block, as the block
        is exited."""
        self.unlock()
        return False  # Indicates that errors should NOT be suppressed.


class AsyncCall(threading.Thread):
    """
    A specialized thread to call a function asynchronously and capture the return value or exception info when it
    becomes available.
    """

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        super().__init__(group, self._target_wrapper, name, args, kwargs, daemon=daemon)
        self._wrapped_target = target
        self.terminated = False
        self.return_value = None
        self.exception = None
        self.traceback = None
        self.exc_info = (None, None, None)

    def _target_wrapper(self, *args, **kwargs):
        """
        Wraps the target function, capturing its return value or exception info.
        """
        pythoncom.CoInitialize()
        try:
            if self._wrapped_target:
                self.return_value = self._wrapped_target(*args, **kwargs)
            self.terminated = True
        except Exception as exc:
            self.exception = exc
            self.traceback = traceback.format_exc()
            self.exc_info = sys.exc_info()
            raise
        finally:
            pythoncom.CoUninitialize()


def async(function, *args, **kwargs):
    """
    Asynchronously call a function, returning an AsyncCall object through which the return value or exception info can
    be accessed once the call completes.

    :param function: The function to call in the background.
    :param args: The arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    :return: An AsyncCall object through which the return value or exception info can be accessed.
    """
    thread = AsyncCall(target=function, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread
