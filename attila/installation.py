"""
Installation mechanisms for attila.
"""

from importlib.machinery import SourceFileLoader

from setuptools import setup as _setup
from setuptools import find_packages
from setuptools.command.install import install as _install

from .abc.files import Path
# from .configurations import get_attila_config_manager, get_automation_config_manager
from .exceptions import verify_type
# from .fs.local import local_fs_connection


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


# # noinspection PyPep8Naming,PyClassHasNoInit
# class config_install(_install):
#     """
#     Extends the standard setuptools "install" command to do some additional work.
#     """
#
#     def run(self):
#         """
#         Run the command.
#         """
#         result = super().run()
#
#         # Determine the root folder where the config files will be installed
#         install_path = Path(self.config_vars['install_path'])
#
#         # For each config file, copy it into the root folder, preserving the folder structure.
#         for config_file in self.config_vars['config_files']:
#             config_file = Path(config_file)
#             destination = install_path / config_file
#             if destination.dir and not destination.dir.is_dir:
#                 destination.dir.make_dir()
#             config_file.copy_to(destination, overwrite=True)
#
#         return result
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
#             config_file = str(abs(config_file))
#         verify_type(config_file, str, non_empty=True)
#         assert Path(config_file).verify_is_file()
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
#     # TODO:
#     #   * Convert all config paths to relative form. (We should make a Path method to do this
#     #     easily, if one doesn't already exist.)
#     #   * Add config paths to package data so they get dumped into the dist.
#
#     # We have to include the config paths and install path as keyword args so config_install can
#     # see them.
#     kwargs['install_path'] = install_path
#     kwargs['config_files'] = config_files
#
#     # The zip_safe argument must be set to False to ensure that the config files get extracted
#     # during installation, making them available to config_install when it copies them to the
#     # install path.
#     kwargs['zip_safe'] = False
#
#     result = _setup(*args, **kwargs)
#
#     return result
