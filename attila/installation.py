"""
Installation mechanisms for attila.
"""

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
# from .configurations import get_attila_config_manager, get_automation_config_manager
from .exceptions import verify_type
# from .fs.local import local_fs_connection


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
                warnings.warn("Unable to load the module to run post-install hooks. Configuration"
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


# # noinspection PyPep8Naming,PyClassHasNoInit
# class config_install(_install):
#     """
#     Extends the standard setuptools "install" command to do some additional work.
#     """
#
#     # user_options = [
#     #     ('install_path=', None, 'Specify the path where the config file is installed.'),
#     #     ('config_files=', None, 'Specify the config file(s) to be installed.')
#     # ]
#     #
#     # def initialize_options(self):
#     #     self.install_path = self.config_vars['install_path']
#     #     self.config_files = self.config_vars['config_files']
#     #     self.
#     #
#     # def finalize_options(self):
#     #     verify_type(self.install_path, str, non_empty=True)
#     #     verify_type(self.config_files, list, non_empty=True)
#     #     self.install_path = Path(self.install_path)
#     #     self.config_files = [Path(path) for path in self.config_files]
#
#     def run(self):
#         """
#         Run the command.
#         """
#         result = super().run()
#
#         # Determine the root folder where the config files will be installed
#         install_path = Path(self.distribution.install_path)
#         print(install_path)
#
#         # For each config file, copy it into the root folder, preserving the folder structure.
#         for config_file in self.distribution.config_files:
#             print(config_file)
#             config_file = Path(config_file)
#             destination = install_path / config_file
#             if destination.dir and not destination.dir.is_dir:
#                 destination.dir.make_dir()
#             config_file.copy_to(destination, overwrite=True)
#
#         return result
#
#
# def _add_config_info(install_path, config_files):
#     verify_type(install_path, str, non_empty=True)
#     verify_type(config_files, list, non_empty=True)
#     def wrapper(dist):
#         print("HI")
#         dist.install_path = Path(install_path)
#         dist.config_files = [Path(path) for path in config_files]
#         return config_install(dist)
#     return wrapper
#
#
# def config_setup(*args, config_files, automation_name=None, **kwargs):
#     """
#     Drop-in replacement for setuptools.setup(), tailored for the distribution of configuration
#     files.
#     """
#
#     # Verify automation name.
#     verify_type(automation_name, str, non_empty=True, allow_none=True)
#
#     # Verify and normalize config file paths.
#     normalized_config_files = []
#     for config_file in config_files:
#         if isinstance(config_file, Path):
#             verify_type(config_file.connection, local_fs_connection)
#         else:
#             verify_type(config_file, str, non_empty=True)
#             config_file = Path(config_file)
#         config_file = config_file - Path()  # Relative to the current path
#         config_file.verify_is_file()
#         normalized_config_files.append(config_file)
#     config_files = normalized_config_files
#
#     # Get the installation requirements.
#     if 'install_requires' in kwargs:
#         install_requires = kwargs['install_requires']
#         verify_type(install_requires, list)
#     else:
#         install_requires = []
#         kwargs['install_requires'] = install_requires
#
#     # Determine the path where the config files should be placed. If an automation name was
#     # specified, make sure the automation is included in the installation requirements.
#     if automation_name is None:
#         automation_name = 'automation'
#         manager = get_attila_config_manager()
#         install_path = str(abs(manager.load_option('Environment', 'Automation Root', Path)))
#     else:
#         for requirement in install_requires:
#             if (requirement == automation_name or
#                     (requirement.startswith(automation_name) and
#                      requirement[len(automation_name):].strip()[:1] in '<>=!')):
#                 break
#         else:
#             install_requires.append(automation_name)
#
#         manager = get_automation_config_manager()
#         manager.set_option('Environment', 'Automation Name', automation_name)
#         install_path = str(abs(manager.load_option('Environment', 'Preferred Config Path')))
#
#     # Get the package data.
#     if 'package_data' in kwargs:
#         package_data = kwargs['package_data']
#         verify_type(package_data, dict)
#     else:
#         package_data = {}
#         kwargs['package_data'] = package_data
#
#     # Get the package data specific to the automation
#     if automation_name in package_data:
#         automation_data = package_data[automation_name]
#         verify_type(automation_data, list)
#     else:
#         automation_data = []
#         package_data[automation_name] = automation_data
#
#     # Add config paths to package data so they get dumped into the dist.
#     automation_data.extend(path - Path(automation_name) for path in config_files)
#
#     # We have to include the config paths and install path as keyword args so config_install can
#     # see them.
#     kwargs['install_path'] = install_path
#     kwargs['config_files'] = [str(path) for path in config_files]
#     print(install_path, config_files)
#
#     # The zip_safe argument must be set to False to ensure that the config files get extracted
#     # during installation, making them available to config_install when it copies them to the
#     # install path.
#     kwargs['zip_safe'] = False
#
#     # This is just to eliminate warnings generated from using ** magic with infotags.get_info(...)
#     if 'doc' in kwargs:
#         del kwargs['doc']
#
#     package_name = kwargs['name']
#     verify_type(package_name, str, non_empty=True)
#
#     # Get the cmdclass (command class) argument from the keyword args.
#     if 'cmdclass' in kwargs:
#         cmdclass = kwargs['cmdclass']
#         verify_type(cmdclass, dict)
#     else:
#         cmdclass = {}
#         kwargs['cmdclass'] = cmdclass
#
#     # If a install command class has not been set, set it to ours. If it has already been set,
#     # assume the user knows what they're doing.
#     if 'install' not in cmdclass:
#         cmdclass['install'] = _add_config_info(install_path, config_files)
#
#     # If the py_modules and packages arguments do not appear in the keyword args, use
#     # find_packages() to locate them.
#     if not ('py_modules' in kwargs or 'packages' in kwargs):
#         kwargs['packages'] = find_packages()
#
#     return _setup(*args, **kwargs)


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
