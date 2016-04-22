"""
attila.processes
================

Tools for controlling and interacting with Windows processes.
"""


import time


import pywintypes
import win32api
import win32com.client
import win32con


from .utility import only
from .exceptions import TooFewItemsError, verify_type, verify_callable


__author__ = 'Aaron Hosford'
__all__ = [
    "process_exists",
    "count_processes",
    "get_pids",
    "get_name",
    "get_parent_pid",
    "get_child_pids",
    "kill_process",
    "kill_process_family",
    "capture_process"
]


# Exit code can be any integer. I picked the binary representation of the
# string "TERM" as the default used when a process is forced to terminate.
DEFAULT_TERMINATION_EXIT_CODE = 1413829197


def process_exists(pid=None, name=None):
    """
    Return a Boolean indicating whether a process exists.

    :param pid: The process ID.
    :param name: The process name.
    :return: Whether the indicated process exists.
    """

    return count_processes(pid, name) > 0


def count_processes(pid=None, name=None):
    """
    Count the number of active processes. If a process ID or process name is provided, count only
    processes that match the requirements.

    :param pid: The process ID of the process.
    :param name: The name of the process.
    :return: The number of processes identified.
    """
    counter = 0
    for process in win32com.client.GetObject('winmgmts:').InstancesOf('Win32_Process'):
        if ((pid is None or process.Properties_("ProcessID").Value == pid) and
                (name is None or process.Properties_("Name").Value == name)):
            counter += 1
    return counter


def get_pids(name=None):
    """
    Return a list of process IDs of active processes.

    :param name: The name of the processes.
    :return: The PIDs of the processes.
    """
    results = []
    for process in win32com.client.GetObject('winmgmts:').InstancesOf('Win32_Process'):
        if name is None or process.Properties_("Name").Value == name:
            results.append(process.Properties_("ProcessID").Value)
    return results


def get_name(pid, default=None):
    """
    Return the name of the process if it exists, or the default otherwise.

    :param pid: The process ID.
    :param default: The default value to return if the process does not exist.
    :return: The name of the process.
    """
    try:
        return only(
            process.Properties_("Name").Value
            for process in win32com.client.GetObject('winmgmts:').InstancesOf('Win32_Process')
            if process.Properties_("ProcessID").Value == pid
        )
    except TooFewItemsError:
        return default


def get_parent_pid(pid):
    """
    Return the process ID of the parent process. If no parent, return None.

    :param pid: The process ID of the child process.
    :return: The process ID of the parent process, or None.
    """

    wmi = win32com.client.GetObject('winmgmts:')
    # noinspection SqlDialectInspection,SqlNoDataSourceInspection
    parent_pids = wmi.ExecQuery(
        'SELECT ParentProcessID FROM Win32_Process WHERE ProcessID=%s' % pid
    )
    if not parent_pids:
        return None
    return only(parent_pids).Properties_('ParentProcessID').Value


def get_child_pids(pid):
    """
    Return the process IDs of the child processes in a list.

    :param pid: The process ID of the parent process.
    :return: A list of the child process IDs.
    """

    wmi = win32com.client.GetObject('winmgmts:')
    # noinspection SqlNoDataSourceInspection,SqlDialectInspection
    children = wmi.ExecQuery('SELECT * FROM Win32_Process WHERE ParentProcessID = %s' % pid)
    return [child.Properties_('ProcessId').Value for child in children]


def kill_process(pid, exit_code=None):
    """
    Kill a specific process.

    :param pid: The process ID of the process to be terminated.
    :param exit_code: The exit code that the terminated process should return. (Default is
        DEFAULT_TERMINATION_EXIT_CODE.)
    :return: Whether the process was successfully terminated.
    """

    if exit_code is None:
        exit_code = DEFAULT_TERMINATION_EXIT_CODE

    try:
        handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
    except pywintypes.error:
        return False  # "The parameter is incorrect."

    if not handle:
        return False

    try:
        win32api.TerminateProcess(handle, exit_code)
        return True
    except pywintypes.error:
        return False  # "Access is denied."
    finally:
        win32api.CloseHandle(handle)


def kill_process_family(pid, exit_code=None, timeout=None):
    """
    Kill a specific process and all descendant processes.

    :param pid: The process ID of the root process to terminate.
    :param exit_code: The exit code to be returned by each terminated process.
    :param timeout: The maximum time in seconds to continue trying to kill the processes.
    :return: None
    """

    if timeout is not None:
        end_time = time.time() + timeout
    else:
        end_time = None
    while True:
        children = get_child_pids(pid)
        if not children:
            break
        if end_time is not None and time.time() >= end_time:
            raise TimeoutError("Unable to kill child processes.")
        for child in children:
            kill_process_family(child, exit_code)
    kill_process(pid, exit_code)


def capture_process(command, process_name=None, closer=None, args=None, kwargs=None):
    """
    Call the command and capture its return value. Watch for a unique process to be created by the
    command, and capture its PID. If a unique new process could not be identified, raise an
    exception. If anything goes wrong after the command is called, and a closer has been provided,
    pass the return value from the command to the closer before raising the exception.

    :param command: A Python callable (a function, method, lambda, or class initializer).
    :param process_name: The expected name of the process that will be created by the command.
    :param closer: A Python callable that releases resources if an exception occurs.
    :param args: Arguments to be passed to the command.
    :param kwargs: Keyword arguments to be passed to the command.
    :return: A pair, (result, pid), where result is the return value of the command and pid is the
        new process ID.
    """
    verify_callable(command)
    verify_type(process_name, str, non_empty=True, allow_none=True)
    verify_callable(closer, allow_none=True)

    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}

    wmi = win32com.client.GetObject('winmgmts:')

    before = {
        process.Properties_("ProcessID").Value: process
        for process in wmi.InstancesOf('Win32_Process')
        if (process_name is None or process.Properties_("Name").Value == process_name)
    }

    result = command(*args, **kwargs)
    try:
        after = {
            process.Properties_("ProcessID").Value: process
            for process in wmi.InstancesOf('Win32_Process')
            if process.Properties_("Name").Value == process_name
        }

        new_pids = set(after) - set(before)

        return result, only(new_pids)
    except:
        if closer is not None:
            closer(result)
        raise
