# Built In
import configparser
import os
import re
import time

# 3rd Party
import appdirs

# Same Package
import attila.env


__author__ = 'Aaron Hosford'


def get_environment_config_search_paths():
    """
    Returns a list of paths to search for environment parameter values, in the order they should be searched.
    """

    user_folder = attila.env.user_config_root()
    site_folder = attila.env.site_config_root()

    candidates = [
        # ----------
        # User-Level
        # ----------

        os.path.join(user_folder, 'environment.ini'),

        # ----------
        # Site-Level
        # ----------

        os.path.join(site_folder, 'environment.ini'),
    ]

    results = []
    for path in candidates:
        if path not in results and os.path.isfile(path):
            results.append(path)

    return results


def get_default_config_search_paths(process_name=None, project_name=None, user_root=None, site_root=None):
    """
    Returns a list of paths to search for "local" (script-specific) parameter values, in the order they should be
    searched.
    """

    process_name = process_name or attila.env.get_package_name(default='shared')
    assert isinstance(process_name, str)

    project_name = project_name or attila.env.get_package_name(default=process_name).split('.')[0] or process_name
    assert isinstance(project_name, str)

    user_folder = user_root or appdirs.user_config_dir('automation', '')
    project_folder = os.path.join(user_folder, project_name)
    site_folder = site_root or appdirs.site_config_dir('automation', '')

    package_folder = attila.env.get_package_folder()
    assert os.path.isdir(package_folder)

    # List the paths in order from most specific to least specific.

    candidates = [
        # -------------
        # Process-Level
        # -------------

        os.path.join(project_folder, process_name + '.ini'),

        # -------------
        # Project-Level
        # -------------

        os.path.join(project_folder, 'project.ini'),

        # ----------
        # User-Level
        # ----------

        os.path.join(user_folder, 'defaults.ini'),

        # ----------
        # Site-Level
        # ----------

        os.path.join(site_folder, 'defaults.ini'),

        # -------------
        # Package-Level
        # -------------

        os.path.join(package_folder, 'defaults.ini'),
    ]

    results = []
    for path in candidates:
        if path not in results and os.path.isfile(path):
            results.append(path)

    return results


class AdvancedInterpolation(configparser.ExtendedInterpolation):

    _DATE_REGEX = re.compile(r"\$\{[^}]*%[^}]*\}")

    def __init__(self, previous=None, env=None):
        super().__init__()
        assert not previous or isinstance(previous, configparser.ConfigParser)
        self._previous = previous
        self._env = dict(env or {})

    def replace_default(self, section, option, value):
        if not self._previous or (value and '${default}' not in value):
            return value

        default_value = ''
        if self._previous and section in self._previous and option in self._previous[section]:
            default_value = self._previous[section][option]

        if '${default}' in value:
            default_value = ''
            if self._previous and section in self._previous and option in self._previous[section]:
                default_value = self._previous[section][option]
            return value.replace('${default}', default_value)
        else:
            return value or default_value

    def replace_env(self, value):
        for name, replacement in self._env.items():
            key = '${' + name + '}'
            value = value.replace(key, replacement)
        return value

    def replace_datetimes(self, value):
        while True:
            replacements = []
            for match in self._DATE_REGEX.finditer(value):
                substring = value[match.start():match.end()][2:-1]
                try:
                    timestring = time.strftime(substring)
                except ValueError:
                    continue
                if substring != timestring:
                    replacements.append((match.start(), match.end(), timestring))

            if not replacements:
                return value

            last_end = 0
            new_value = ''
            for start, end, replacement in replacements:
                new_value += value[last_end:start] + replacement
                last_end = end
            new_value += value[last_end:]

            value = new_value

    def before_get(self, parser, section, option, value, defaults):
        value = self.replace_default(section, option, value)
        value = self.replace_datetimes(value)
        value = self.replace_env(value)
        return super().before_get(parser, section, option, value, defaults)


def load_params(*paths, default=False, environment=False, translate=True, replacements=None, project=None, process=None):
    """
    Load the parameter values from the parameter files. Parameter files are searched in order, and the value for each
    parameter is the one from the first file found that defines that parameter. If local_params is set (or if no paths
    are provided and global_params is not set), the script-specific parameters are searched in order of decreasing
    specificity after any other paths provided to the function. If global_params is set, the global parameters are then
    searched as well, again in order of decreasing specificity. See get_default_config_search_paths() and
    get_environment_config_search_paths() for the specific paths that are searched, and their search order.
    """

    replacements = dict(replacements or {})

    if default or not (paths or environment):
        paths += tuple(get_default_config_search_paths())

        if translate:
            package_name = attila.env.get_package_name(default='anonymous')
            package_path = attila.env.get_package_folder()

            process = process or package_name
            project = project or process

            if project == process:
                project_and_process = process
            else:
                project_and_process = os.path.join(project, process)

            replacements.update(
                {
                    'project': project,
                    'process': process,

                    'package_name': package_name,
                    'package_path': package_path,

                    'user_data': os.path.join(attila.env.user_data_root(), project_and_process),
                    'site_data': os.path.join(attila.env.site_data_root(), project_and_process),

                    'user_project_data': os.path.join(attila.env.user_data_root(), project),
                    'site_project_data': os.path.join(attila.env.site_data_root(), project),

                    'user_log': os.path.join(attila.env.user_log_root(), project),
                    'site_log': os.path.join(attila.env.site_log_root(), project),
                }
            )

    if environment:
        paths += tuple(get_environment_config_search_paths())

        # if translate:
        #     home_folder = get_automation_home()
        #     assert os.path.isdir(home_folder)
        #
        #     replacements['%automation_home%'] = home_folder

    parser = configparser.ConfigParser(
        defaults=replacements,
        allow_no_value=True,
        strict=False
    )
    for path in paths:
        if translate:
            parser = configparser.ConfigParser(
                allow_no_value=True,
                strict=False,
                interpolation=AdvancedInterpolation(parser, replacements)
            )

        parser.read(path)

    return parser
