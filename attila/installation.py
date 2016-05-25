"""
Installation mechanisms for attila.
"""

import os

from importlib.machinery import SourceFileLoader

from setuptools import setup as _setup
from setuptools import find_packages
from setuptools.command.install import install as _install

from .exceptions import verify_type


__author__ = 'Aaron Hosford'


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

        # Find the package
        package_name = self.config_vars['dist_name']
        for path in package_name + '.py', os.path.join(package_name, '__init__.py'):
            if os.path.isfile(path):
                import_path = os.path.abspath(path)
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
            return result

        # Call the post-install hook.
        if (hasattr(module, 'main') and hasattr(module.main, 'context') and
                hasattr(module.main.context, 'post_install_hook')):
            module.main.context.post_install_hook()

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

    # Commented this out due to faulty assumptions. We don't want to force libraries to have a
    # console script entry point.
    # # Get the entry_points argument from the keyword args.
    # if 'entry_points' in kwargs:
    #     entry_points = kwargs['entry_points']
    #     verify_type(entry_points, dict)
    # else:
    #     entry_points = {}
    #     kwargs['entry_points'] = entry_points
    #
    # # Get the console_scripts section from the entry points.
    # if 'console_scripts' in entry_points:
    #     console_scripts = entry_points['console_scripts']
    #     verify_type(console_scripts, list)
    # else:
    #     console_scripts = []
    #     entry_points['console_scripts'] = console_scripts
    #
    # # Add the script's main() as a console script entry point.
    # for entry_point in console_scripts:
    #     verify_type(entry_point, str, non_empty=True)
    #     name = entry_point.split('=')[0]
    #     if name == package_name:
    #         break
    # else:
    #     console_scripts.append(
    #         '{package_name} = {package_name}:main'.format(package_name=package_name)
    #     )

    return _setup(*args, **kwargs)
