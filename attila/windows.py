"""
attila.windows
==============

Functions for dealing with windows.
"""

import logging
import os
import re


import pywintypes
import win32con
import win32gui
import win32process


import attila.processes
import attila.strings
import attila.threads


log = logging.getLogger(__name__)


# It's not a publicly visible type, so we have to resort to this silliness...
REGEX_TYPE = type(re.compile(''))


def set_title(title):
    """
    Set the title for the console window of the script.

    :param title: The new title of the console window.
    :return: None
    """

    log.info("Setting window title to " + repr(title) + ".")

    if os.system('TITLE ' + title):
        raise RuntimeError("Unable to set window title to " + repr(title) + ".")


def window_exists(title):
    """
    Return a Boolean value indicating whether a window with the given title exists.

    :param title: The title of the window to search for.
    :return: Whether a window with the given title exists.
    """
    return win32gui.FindWindow(None, title) > 0


def _force_close_window_callback(hwnd, title_regex):
    """
    Passed to win32gui.EnumWindows by force_close_window() to handle the closing of each individual window. If the title
    regex isn't matched, the window is ignored. If it matches, we successively try various methods to politely get the
    window to close. If none of them work, we resort to killing the process family.

    :param hwnd: The window handle being examined.
    :param title_regex: The regex the title of the window is supposed to be matched by.
    :return: None
    """

    assert isinstance(title_regex, REGEX_TYPE)

    title = str(win32gui.GetWindowText(hwnd))

    if re.match(title_regex, title) is None:
        # The title of this window doesn't match, so it's not one we're supposed to close.
        log.debug("Ignoring window with title '%s' and handle %s.", title, hwnd)
        return

    log.debug("Closing window with title '%s' and handle %s.", title, hwnd)

    # Send a polite "close window" message.
    log.debug("Sending WM_CLOSE.")
    try:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    except pywintypes.error as exc:
        if "Invalid window handle." in str(exc):
            return  # It doesn't exist, so nothing to do.
        elif "Access is denied." in str(exc):
            pass  # We'll have to do it a different way.
        else:
            raise  # This is unexpected...

    # Wait for it to work.
    attila.threads.wait_for_handle(hwnd, 10)

    # Send a polite "quit program" message.
    log.debug("Sending WM_QUIT.")
    try:
        win32gui.PostMessage(hwnd, win32con.WM_QUIT, 0, 0)
    except pywintypes.error as exc:
        if "Invalid window handle." in str(exc):
            return  # It doesn't exist, so nothing to do.
        elif "Access is denied." in str(exc):
            pass  # We'll have to do it a different way.
        else:
            raise  # This is unexpected...

    # Wait for it to work.
    attila.threads.wait_for_handle(hwnd, 10)

    # Murder the process and all its children. We're done.
    log.debug("Killing process family.")
    thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
    attila.processes.kill_process_family(process_id, timeout=10)


def force_close_windows(title_pattern):
    """
    Force-close all windows with a title matching the provided pattern.

    :param title_pattern: A regex or a glob-style pattern string indicating which windows to force-close.
    :return: None
    """
    log.debug("Force-closing window(s) with title matching '%s'.", title_pattern)
    if not isinstance(title_pattern, REGEX_TYPE):
        title_pattern = attila.strings.glob_to_regex(title_pattern)
    win32gui.EnumWindows(_force_close_window_callback, title_pattern)
