"""
Installation mechanisms for attila.
"""

# TODO: Add an Environment:On Installation option in attila.ini, to allow, for example, the
#       automatic notification and/or logging of the currently installed version of a
#       library or automation on each server.

import sys
import traceback
import warnings

from importlib.machinery import SourceFileLoader
from functools import partial

from setuptools import setup as _setup
from setuptools import find_packages
from setuptools.command.install import install as _install
from setuptools.dist import DistutilsSetupError

from .abc.files import Path
from .exceptions import verify_type


__author__ = 'Aaron Hosford'


_POST_INSTALL_DESIGNATOR = '__post_install__'
_PRE_UNINSTALL_DESIGNATOR = '__pre_uninstall__'


# noinspection PyPep8Naming,PyClassHasNoInit
class install(_install):
    """
    Extends the standard setuptools "install" command to do some additional work.
    """

    def run(self):
        """
        Run the command.
        """
        result = super().run()

        try:
            # Find the package
            package_name = self.config_vars['dist_name']
            for path in Path(package_name + '.py'), Path(package_name) / '__init__.py':
                if path.is_file:
                    import_path = str(abs(path))
                    break
            else:
                # Nothing to do; we can't find the module to import it.
                return result

            # Import the package.
            # noinspection PyBroadException
            try:
                module = SourceFileLoader(package_name, import_path).load_module()
            except Exception:
                # We couldn't import it, so we definitely can't call the post-install hook.
                traceback.print_exc()
                warnings.warn("Unable to load the module to run post-install hooks. Configuration "
                              "files will have to be copied manually, and functions labeled with "
                              "the '@post_install' decorator will need to be called manually.")
                return result

            post_installs = {}

            # Make sure we include the attila auto_context post-install hook.
            if (hasattr(module, 'main') and hasattr(module.main, 'context') and
                    hasattr(module.main.context, 'post_install_hook')):
                post_installs[0] = [module.main.context.post_install_hook]

            for name in dir(module):
                value = getattr(module, name)
                if callable(value) and hasattr(value, _POST_INSTALL_DESIGNATOR):
                    index = getattr(value, _POST_INSTALL_DESIGNATOR)
                    if index in post_installs:
                        post_installs[index].append(value)
                    else:
                        post_installs[index] = [value]

            # Call the post-install hooks.
            for index in sorted(post_installs):
                for hook in post_installs[index]:
                    hook()

        except Exception as exc:
            traceback.print_exc()

            error_type, error_value, error_traceback = sys.exc_info()
            error_message = ''.join(traceback.format_exception_only(error_type, error_value))
            error_message = error_message.strip()

            # If it isn't raised as this error type, the error message may be obscured due to a
            # known distutils bug/feature.
            raise DistutilsSetupError('Error in post-install hook:\n' + error_message) from exc

        return result


def setup(*args, **kwargs):
    """
    Drop-in replacement for setuptools.setup(). See documentation for setuptools.setup() for full
    documentation of the accepted arguments.
    """

    # See https://pythonhosted.org/setuptools/setuptools.html#new-and-changed-setup-keywords for a
    # list of keywords accepted by setuptools.setup(). See
    # https://docs.python.org/3.4/distutils/apiref.html for additional keywords accepted by
    # distutils.core.setup() and for the most part also accepted by setuptools.setup().

    # This is just to eliminate warnings generated from using ** magic with infotags.get_info(...)
    if 'doc' in kwargs:
        del kwargs['doc']

    package_name = kwargs['name']
    verify_type(package_name, str, non_empty=True)

    # Get the cmdclass (command class) argument from the keyword args.
    if 'cmdclass' in kwargs:
        cmdclass = kwargs['cmdclass']
        verify_type(cmdclass, dict)
    else:
        cmdclass = {}
        kwargs['cmdclass'] = cmdclass

    # If a install command class has not been set, set it to ours. If it has already been set,
    # assume the user knows what they're doing.
    if 'install' not in cmdclass:
        cmdclass['install'] = install

    # If the py_modules and packages arguments do not appear in the keyword args, use
    # find_packages() to locate them.
    if not ('py_modules' in kwargs or 'packages' in kwargs):
        kwargs['packages'] = find_packages()

    return _setup(*args, **kwargs)


# TODO: Add a similar mechanism for pre-uninstall hooks. (It doesn't appear to be straight forward
#       when using pip.)
def post_install(function, index=None):
    """
    A decorator for registering a function to be called immediately after install of the containing
    package. The function must accept zero parameters. The return value will be ignored.

    :param function: The function to be called after installation.
    :param index: The precedence of the function relative to other post-install functions.
    :return: The function, tagged with a post-install designator.
    """

    if isinstance(function, (int, float)):
        assert index is None
        return partial(post_install, index=function)

    assert callable(function)
    assert isinstance(function, object)
    verify_type(index, (int, float), allow_none=True)

    if index is None:
        index = 1

    setattr(function, _POST_INSTALL_DESIGNATOR, index)
    return function
