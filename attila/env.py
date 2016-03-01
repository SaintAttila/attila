# Built In
import os
import sys

# 3rd Party
import appdirs

__author__ = 'Aaron Hosford'


# The globals dict of __main__, if it has been provided to init(), or else None.
MAIN_GLOBALS = None


def init(main_globals_dict):
    """
    Initialization of the automation environment. This function should be called at the beginning of execution.
    """

    global MAIN_GLOBALS, AUTOMATION_HOME
    MAIN_GLOBALS = main_globals_dict


def get_main_globals():
    """
    Return the globals dict (as returned by globals()) of __main__, or as close an approximation to it as possible if
    init() has not yet been called.
    """

    if MAIN_GLOBALS:
        # If the globals dict has been provided, great!
        return MAIN_GLOBALS
    elif '__main__' in sys.modules:
        # This doesn't have everything that the globals dict has, but it's better than nothing.
        return sys.modules['__main__'].__dict__
    else:
        # Worst case scenario: We know nothing about the calling environment.
        return {}


def get_package_name(globals_dict=None, default=None, use_cwd=True, errors=False):
    """
    Accept the globals dict returned by calling globals() in the script, module, or package of interest, and return a
    name for that script, module, or package which is suitable for use as a base for log and parameter file names. If no
    good name can be identified, returns the default. If use_cwd flag is set, this function will fall back on the
    current working directory when all else fails. The errors flag controls whether errors can ever be raised; by
    default, this is set to False to ensure that the function is safe to call before error logging/reporting has been
    setup.

    Example Usage:
        name_of_this_module = get_package_name(globals(), default='anonymous')
    """

    try:
        # Default to the globals dict returned by get_main_globals()
        if globals_dict is None:
            globals_dict = get_main_globals()

        # The easiest place to look is the __package__ attribute of the main module, if it exists.
        name = globals_dict.get('__package__', None)
        if name:
            while name.split('.')[-1].startswith('__'):
                name = '.'.join(name.split('.')[:-1])
            if name and not name.startswith('__'):
                return name

        # We use the __file__ attribute of the main module, if it's available, or the current working directory
        # otherwise.
        path = globals_dict.get('__file__', None)
        if not path and use_cwd:
            path = os.getcwd()

        # If the main module is inside a package, go up the folder hierarchy until we find the first one that contains
        # a __main__.py, or the last one that contains an __init__.py, and then use that folder's name. Otherwise, use
        # the name of the main module, minus the ".py".
        if path:
            parent = os.path.dirname(path)
            has_init = False
            while (os.path.isfile(os.path.join(parent, '__init__.py')) and
                   not os.path.isfile(os.path.join(parent, '__main__.py'))):
                path = parent
                has_init = True
                parent = os.path.dirname(path)
                if parent == path:
                    break
            name = os.path.basename(path)
            if name in ('__init__.py', '__main__.py') or (os.path.isfile(path) and
                                                          os.path.isfile(os.path.join(parent, '__init__.py'))):
                path = parent
                name = os.path.basename(path)
            if name:
                if name.endswith('.py'):
                    return name[:-3]
                if has_init or os.path.isfile(os.path.join(path, '__main__.py')) or len(name.split()) == 1:
                    # Strip < and > because PyScripter adds these for unsaved modules.
                    return name.lstrip('<').rstrip('>')

        # If somehow we still haven't found a suitable name, use __name__, but only if it isn't double-underscored.
        name = globals_dict.get('__name__', None)
        if name:
            name = name.split('.')[0]
            if name and not name.startswith('__'):
                return name

        # And if all else fails, return our default.
        return default
    except Exception:
        if errors:
            return default
        raise


def get_package_folder(globals_dict=None, default=None, use_cwd=True, errors=False):
    """
    Accept the globals dict returned by calling globals() in the script, module, or package of interest, and return a
    path to a folder which is suitable for use as a base for log and parameter file paths for that script, module, or
    package. If no good name can be identified, returns the default. If use_cwd flag is set, this function will fall
    back on the current working directory when all else fails. The errors flag controls whether errors can ever be
    raised; by default, this is set to False to ensure that the function is safe to call before error logging/reporting
    has been setup.

    Example Usage:
        root_folder = get_package_folder(globals())
    """

    try:
        # Default to the globals dict returned by get_main_globals()
        if globals_dict is None:
            globals_dict = get_main_globals()

        # If no default is provided, fall back on the current working directory.
        if use_cwd and not default:
            default = os.getcwd()

        # We use the __file__ attribute of the main module, if it's available, or the current working directory
        # otherwise.
        path = globals_dict.get('__file__', None)
        if not path and use_cwd:
            path = os.getcwd()

        # Work our way up the folder hierarchy until we find a folder that contains a __main__.py, or whose parent
        # doesn't contain an __init__.py.
        if path:
            parent = os.path.dirname(path)
            while (os.path.isfile(os.path.join(parent, '__init__.py')) and
                   not os.path.isfile(os.path.join(parent, '__main__.py'))):
                path = parent
                parent = os.path.dirname(path)
                if parent == path:
                    break
            if parent and (os.path.isfile(path) or
                           (os.path.isfile(os.path.join(path, '__init__.py')) and
                            not os.path.isfile(os.path.join(path, '__main__.py')))):
                return parent
            elif os.path.isdir(path):
                return path
            elif os.path.isdir(parent):
                return parent

        # Failing that, just use the default value.
        return default
    except Exception:
        if errors:
            return default
        raise


def user_config_root():
    return appdirs.user_config_dir('automation', '')


def site_config_root():
    return appdirs.site_config_dir('automation', '')


def package_config_root():
    return os.path.join(attila.env.get_package_folder(), 'config')


def user_log_root():
    return appdirs.user_log_dir('automation', '')


def site_log_root():
    return os.path.join(appdirs.site_data_dir('automation', ''), 'logs')


def user_data_root():
    return appdirs.user_data_dir('automation', '')


def site_data_root():
    return appdirs.site_data_dir('automation', '')


def package_data_root():
    return os.path.join(attila.env.get_package_folder(), 'data')
