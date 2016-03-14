"""
attila.processes
================

Tools for controlling and interacting with Windows processes.
"""


import sys
import threading
import traceback

import pythoncom

from win32com.client import GetObject


from attila.utility import only, TooFewItemsError


__all__ = [
    "get_processes",
    "kill_processes",
    "capture_process",
    "KillProcessTimer",
]


def get_processes(pid=None, name=None):
    """
    Scan the list of running processes for any with the given PID and name. Return a list containing a WMI process
    object for each such process. Note that process name is case sensitive. Will return all running processes if None is
    provided for both fields.

    :param pid: The process ID, an integer.
    :param name: The process name.
    :return: A list of processes.
    """
    return [
        process
        for process in GetObject('winmgmts:').InstancesOf('Win32_Process')
        if ((pid is None or process.Properties_("ProcessID").Value == pid) and
            (name is None or process.Properties_("Name").Value == name))
    ]


def kill_processes(pid=None, name=None):
    """
    Kill all processes matching the given PID and process name. Note that process name is case sensitive.

    :param pid: The process ID, an integer.
    :param name: The process name.
    :return: The number of terminated processes.
    """
    if pid is None and name is None:
        raise ValueError("Either pid or name must be provided.")

    processes = get_processes(pid, name)
    for process in processes:
        # It's a property, not a method, but accessing its value kills the process. Thanks, Microsoft. :-\
        # noinspection PyStatementEffect
        process.Terminate

    return len(processes)


def capture_process(command, process_name=None, closer=None, args=None, kwargs=None):
    """
    Call the command and capture its return value. Watch for a unique process to be created by the command, and capture
    its PID. If a unique new process could not be identified, raise an exception. If anything goes wrong after the
    command is called, and a closer has been provided, pass the return value from the command to the closer before
    raising the exception.

    :param command: A Python callable (a function, method, lambda, or class initializer).
    :param process_name: The expected name of the process that will be created by the command.
    :param closer: A Python callable that releases resources if an exception occurs.
    :param args: Arguments to be passed to the command.
    :param kwargs: Keyword arguments to be passed to the command.
    :return: A pair, (result, pid), where result is the return value of the command and pid is the new process ID.
    """
    assert callable(command)
    assert process_name is None or isinstance(process_name, str)
    assert closer is None or callable(closer)

    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}

    wmi = GetObject('winmgmts:')

    before = {
        process.Properties_("ProcessID").Value : process
        for process in wmi.InstancesOf('Win32_Process')
        if (process_name is None or process.Properties_("Name").Value == process_name)
    }

    result = command(*args, **kwargs)
    try:
        after = {
            process.Properties_("ProcessID").Value : process
            for process in wmi.InstancesOf('Win32_Process')
            if process.Properties_("Name").Value == process_name
        }

        new_pids = set(after) - set(before)

        return result, only(new_pids)
    except:
        if closer is not None:
            closer(result)
        raise


class KillProcessTimer(threading.Timer):
    """
    This is a thread whose sole purpose is to kill another process after a set amount of time has passed. It's necessary
    because sometimes Excel hangs and there is no other clean way to terminate the process.
    """

    def __init__(self, pid, name, timeout):
        self.pid = pid
        self.name = name
        self.timeout = timeout
        self.terminated = False
        self.exception = None
        self.traceback = None
        self.exc_info = (None, None, None)

        threading.Timer.__init__(self, timeout, self.kill_process)

    def kill_process(self):
        """
        Called by the timer to kill the process after the timeout has expired.

        :return: None
        """
        pythoncom.CoInitialize()
        try:
            try:
                process = only(get_processes(self.pid, self.name))
            except TooFewItemsError:
                pass
            else:
                # It's a property, not a method, bu accessing its value kills the process.
                # noinspection PyStatementEffect
                process.Terminate
                self.terminated = True
        except Exception as exc:
            self.exception = exc
            self.traceback = traceback.format_exc()
            self.exc_info = sys.exc_info()
        finally:
            pythoncom.CoUninitialize()
