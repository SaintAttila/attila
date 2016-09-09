"""
Attila Package Generator
========================

Walks the developer through the creation of a new automation package from the
template.


USAGE:

1. Open a command prompt
2. `cd` into the folder where you want to create a new attila project
3. Run the command `new_attila_package`, or, if your path variable isn't setup,
   `python -m attila.generation`.
"""

from ..abc.files import Path
from ..configurations import get_attila_config_manager
from ..fs import getcwd


INTRODUCTION = """
========================
Attila Package Generator
========================

"""


DESCRIPTION_HOW_TO = """
Please paste in a high-level description of the purpose of the new package.
(Please Do NOT go into detail as to how will accomplish that purpose.) It is
highly recommended that you compose your description in a separate editor so
you don't lose your work. Hit return 3 times to end your description.
"""


WRAP_UP = """
The new package has been generated. To get started developing, please use your
preferred editor to search for the keyword, TODO, and follow the directions
provided there.
"""


DEFAULT_URL_TEMPLATE = 'TBD'


TEMPLATE_FILE_SUFFIX = '_template'


def to_title(string):
    """The str.title() method is broken for our purposes. This one works as expected."""
    result = ''
    capitalize = True
    for char in string:
        if char.isspace():
            capitalize = True
            result += char
        elif capitalize:
            result += char.upper()
            capitalize = False
        else:
            result += char
    return result


def ask(option_name, *, default=None, normalize=str.strip, non_empty=True, validate=None):
    """Ask the user for a piece of information in a standardized way."""
    value = None
    option_name = to_title(option_name)
    while True:
        print()
        if default:
            print("Default %s is %s." % (option_name, default))
            print("Provide a different value or hit enter to use the default.")
        value = input('%s: ' % option_name)
        if normalize:
            value = normalize(value)
        if default:
            value = value or default
        if non_empty and not value:
            print("A value must be provided. Please try again.")
        elif validate and not validate(value):
            print("Invalid value. Please try again.")
        else:
            break
    print("%s set to %s." % (option_name, value))
    print()
    return value


def fill_template(target_folder, title, package, author, author_email, url, description, overwrite=None,
                  template_root=None):
    """Create a new package by populating the template with the provided information."""

    title_underbar = '=' * len(title)
    indented_description = description.replace('\n', '\n    ')

    if template_root is None:
        template_root = Path(__file__).dir['_template']

    # Create the package folder
    package_folder = target_folder / package
    package_folder.make_dir(overwrite=True)

    for dir_path, dir_names, file_names in template_root.walk():
        sub_path = Path(str(dir_path - template_root).replace('package', package))
        target_dir = target_folder / sub_path
        target_dir.make_dir(overwrite=True)
        for file_name in file_names:
            source_path = dir_path / file_name
            if file_name.endswith(TEMPLATE_FILE_SUFFIX):
                save_path_tail = sub_path / file_name[:-len(TEMPLATE_FILE_SUFFIX)].replace('package', package)
                save_path = target_folder / save_path_tail
                print("Writing to", save_path)
                if save_path.is_file:
                    if overwrite is None:
                        answer = input("The file %s already exists. Overwrite? (y/n) " % save_path_tail)
                        if not answer.lower().startswith('y'):
                            print("File skipped.")
                            continue
                    elif not overwrite:
                        raise FileExistsError(save_path)
                with source_path.open() as source_file:
                    with save_path.open('w') as save_file:
                        for line in source_file:
                            save_file.write(
                                line.format(
                                    title=title,
                                    title_underbar=title_underbar,
                                    package=package,
                                    author=author,
                                    author_email=author_email,
                                    url=url,
                                    description=description,
                                    indented_description=indented_description
                                )
                            )
            else:
                save_path_tail = sub_path / file_name.replace('package', package)
                save_path = target_folder / save_path_tail
                print('Copying to', save_path)
                if save_path.is_file:
                    if overwrite is None:
                        answer = input("The file %s already exists. Overwrite? (y/n) " % save_path_tail)
                        if not answer.lower().startswith('y'):
                            print("File skipped.")
                            continue

                source_path.copy_to(save_path, overwrite=overwrite)


def main():
    """
    Attila Package Generator
    ========================

    Walks the developer through the creation of a new automation package from the
    template.


    USAGE:

    1. Open a command prompt
    2. `cd` into the folder where you want to create a new attila project
    3. Run the command `new_attila_package`, or, if your path variable isn't setup,
       `python -m attila.generation`.
    """

    manager = get_attila_config_manager()

    section = 'Code Generation'
    default_author = manager.load_option(section, 'Author', str, None)
    default_author_email = manager.load_option(section, 'Author Email', str, None)
    url_template = manager.load_option(section, 'URL Template', str, DEFAULT_URL_TEMPLATE).strip()

    template_path = manager.load_option(section, 'Package Template Path', Path, None)

    print(INTRODUCTION)

    title = ask(
        'project title',
        normalize=lambda value: value.strip().title()
    )

    package = ask(
        'package name',
        default='_'.join(''.join(char if char.isalnum() else ' ' for char in title.lower()).split()),
        validate=lambda value: all(char.isalnum() or char == '_' for char in value)
    )

    author = ask(
        "author's full name",
        default=default_author,
        normalize=lambda value: to_title(' '.join(value.split())),
        validate=lambda value: len(value.split()) > 1 and not any(char.isdigit() for char in value)
    )

    if not default_author_email:
        default_author_email = '.'.join(
            ''.join(char if char.isalpha() else ' ' for char in author.lower()).split()
        ) + '@ericsson.com'

    author_email = ask(
        "author's email address",
        default=default_author_email,
        validate=lambda value: '@' in value and not any(char.isspace() for char in value)
    )

    url = ask(
        "project url",
        default=url_template.format(title=title, package=package),
        validate=lambda value: value.lower().startswith('http') and not value.lower().endswith('.git')
    )

    print(DESCRIPTION_HOW_TO)
    description = ''
    while not description.strip() or not description.endswith('\n\n\n'):
        description += input('> ') + '\n'
    description = description.strip('\n')

    print("Filling the template to generate your new package...")
    fill_template(getcwd(), title, package, author, author_email, url, description, template_root=template_path)

    print(WRAP_UP)
