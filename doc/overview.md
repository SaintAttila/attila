# Attila

## Introduction

### What is an "automation"?

Before going into what Attila is and does, it's important to understand 
the programming paradigm it's intended for. Attila was built to 
facilitate the development and maintenance of _automations_. What's an 
automation? An automation is a piece of software specifically designed 
to run autonomously, without supervision or intervention, in unobserved 
environments like remote servers, or PCs and laptops during off hours.
Automations differ from more familiar forms of software in that their
interfaces are seldom interactive - instead typically taking the form 
of a simple window with scrolling log or status messages - and they are
typically controlled through a task scheduler, command prompts, and/or
parameter files. In this respect, they closely resemble OS services, but
they differ from services in that they have specific jobs they 
accomplish (e.g. generating reports, sending emails, updating database 
tables, or processing regularly generated files) rather than simply
providing background support for other software. Because of their lack 
of interaction, automations don't really have "users" in the traditional
sense; instead they have _maintainers_, whose job is to keep the
automations functioning properly, and _clients_, which are people or
downstream processes which benefit from the automations' activities.
Automations are subject to much more stringent validation and error
recovery constraints, since for the most part they must be able to
function independently of user supervision or intervention. Unlike most
software, an automation has to be smart enough to do its job all on its 
own, and can't fall back on the actions of a user to guide it towards 
intelligent decisions.

### What is Attila?

With the concept of automation programming defined, Attila's purpose
becomes much easier to express: Attila is not only an automation 
library; it's a _framework_ for building and installing automations. The 
primary goal underlying all of Attila's design is that it should be as 
easy as possible to build, install, and maintain automations. A good 
framework should get out of your way so you can get down to business; it 
should be invisible except when you need it to do something for you. 
With this goal in mind, Attila does its best to minimize the required 
boilerplate code, and to streamline the most common tasks that are 
required of automations and their maintainers. These common tasks 
include interactions with data stores such as databases and files, 
generation of notifications like emails and log messages, dealing with 
parameter file configurations, securely storing and accessing system 
login credentials, interacting with other threads, processes, and 
windows, and installing and updating automations.

### The Automation Environment

Attila assumes a particular model of development: A single development 
shop, operating in a privately controlled, multi-server environment, 
with its own unique standards for how the automations it develops and 
manages should behave. With this in mind, Attila supports the 
configuration of the shared automation environment at the system account 
level on each server. The per-account configuration takes the form of an 
`automation.ini` file installed in the `~/.automation` folder, where `~` 
is used to represent the account's "home" folder. (Linux users will find
this instantly familiar.) It is assumed that if distinct shared 
configurations are required, then these will operate under distinct 
system accounts.

### Abstract Interfaces

Attila provides a layer of abstraction between the configuration of an
automation and its high-level behavior. For example, the generation of a 
notification event is managed separately from the specific type of 
notification that is ultimately generated. This is accomplished through
the use of abstract base classes, together with _configuration loaders_. 
A configuration loader is a class or function, often separately 
installed as an Attila plugin, which parses a config file option or 
section and returns back a first-class object, ready to be used by the 
automation. The configuration file itself indicates which configuration
loaders should be used for which configuration options or sections. The
end result is that, rather than loading a path string from a 
configuration file, determining which local or remote file system the
path refers to, connecting to that system, and operating on the 
indicated file in a unique way depending on the system it resides on,
the automation can simply load a Path object which knows not only its
path string but how to connect to and operate upon the target system. 
The automation can then utilize the standard Path interface to perform
the desired operations on the target file irrespective of what system
it resides on, be it a local file system, FTP, HTTP, or any other
protocol. The same approach is applied to other common points of
variation, such as database access and the previously mentioned event
notification.

#### Important Abstractions

* Connections to remote systems: All connections provide the same
  interface, whether they are to databases, file systems, or other
  types of connections.
* File system interactions: All file systems and paths to objects
  residing on those file systems provide the same interface, whether the
  file system object resides on the local file system, an FTP site, or 
  some other type of system. 
* SQL database interactions: All database interactions are funneled
  through the same interface, including the ability to construct queries
  in an identical manner irrespective of the particular SQL dialect 
  supported by the server.
* Generation of notifications: All notification mechanisms support the
  same interface, whether it is sending of an email, logging to a file,
  or inserting a record in a database table. 

The net result is that an automation can be written in such a way that
it does not know and does not _care_ where it pulls its data from, how
to connect to the remote systems it accesses, where its files come from
or are going, or how the notifications it sends are delivered. All the
automation developer needs to worry about is the high-level logic that
determines if and when these activities are performed. If an automation
has to be pointed to an FTP site instead of a local file system, or use
a MySQL database instead of a sqlite table, or log to a database instead
of sending an email, only the _configuration file_ needs to change; the
code itself is fully generic.

## Setting Up Attila

### Installation Requirements

Installation of Attila requires the setuptools and infotags packages to
already be installed. Because these are install-time dependencies of
`setup.py` itself, they are not automatically installed for you as part
of the installation of Attila. These packages can be installed via the
command `pip install setuptools infotags` command. Once these packages
have been installed, the Attila framework can be installed with 
`pip install attila`. An `automation.ini` will still need to be created 
to configure the automation environment. The individual automations are
packaged and installed separately and should list Attila as a 
dependency.

### The `.automation` Folder

The `.automation` folder is where Attila automations "live" - where they
store parameters, write logs, place documentation, and operate on files.
Having all automation activity localized to a specific folder simplifies
maintenance for systems with large collections of automations.

The `.automation` folder is structured in a fairly straight-forward way.
Files that are utilized by Attila itself or which contain data shared
across multiple automations are placed directly in the `.automation`
folder, whereas each automation has a sub-folder named after itself.
Within each automation sub-folder are four folders, identically named
for every automation, each having a precisely defined purpose: 

* `data`: Data files used by the automation to coordinate its activities
   across multiple executions.
* `docs`: Documentation for maintainers of the process.
* `logs`: Automation-specific log files.
* `workspace`: Temporary storage for files being operated on during a
  single execution. It is recommended that automations utilize this
  folder rather than the system's `temp` folder, since automations often
  benefit from a more organized and controlled working environment, and 
  it also simplifies maintenance and recovery in the event of a crash. 
  
Also appearing in the automation sub-folder is the configuration file
for the automation.

The `.automation` folder typically resides in the user's "home" folder,
denoted by `~` on linux systems and in Attila `Path` objects. On Windows 
this is the `C:\Users\[UserName]` folder.

### Configuring Attila

Topics to be covered in this section:

* Packaging & distributing an environment configuration.
* Managing multiple environment configurations.
* Test mode.
* Overriding the automation package template used by attila.generation.
* Security and password management.
* Customizing logging.
* Controlling event notifications.
* Dealing with database connections.

TODO: Explain for new users and dev shops adopting Attila how to install 
      Attila and configure the automation environment.

## Writing Your First Automation

Attila comes with a built-in automation package template, which you can
access through the attila.generation module or via the 
`new_attila_package` command-line tool which is installed alongside
Attila. By running `new_attila_package` or `python -m attila.generation`
on the command line, Attila will walk you step-by-step through gathering
the information it needs to populate the new package. It will then
create a new package within the current working directory. All that's
left for you to do is populate the parameters in the generated `.ini`
file and fill in the actual logic in `main()`. Some of the behavior of
the package generation mechanisms can be controlled through the
`[Code Generation]` sections in `attila.ini` or `automation.ini`.

## Automation Configuration

Attila provides a simple means for automations to access their working
environments. The `@automation` decorator can be used with the `main`
function to make this functionality available to your automation via
`auto_context.current()`:

    @automation
    def main():
        context = auto_context.current()

The context object provides numerous properties that describe the automation's
runtime environment:

TODO: Add information about the configuration options to each entry here.

* `automation_root`: A `Path` object indicating the location of the "root" 
  `.automation` folder. This is configured via the `Automation Root` option in
  the `Environment` section of `attila.ini`, and can be overridden in 
  `automation.ini`. It defaults to `~/.automation`.
* `automation_start_notifier`, `automation_error_notifier`, 
  `automation_end_notifier`: Each of these properties is a `Notifier` object 
  which is used to automatically transmit notifications indicating the run-time
  status of the automation. You will generally have no need to access these 
  directly. They are configured via the `On Automation Start`, `On Automation 
  Error`, and `On Automation End` options in the `Environment` section of your
  `automation.ini` configuration file. These notifiers are called upon entries,
  unhandled exceptions, and exits (via return or exception) of any function you 
  have used the `@automation` decorator with.
* `data_dir`: A `Path` object indicating the location where persistent data
  files for this automation should be stored.
* `docs_dir`: A `Path` object indicating the location where this automation's
  documentation should be stored.
* `log_dir`: A `Path` object indicating the location where log files generated
  by this automation should be written.
* `manager`: A `ConfigManager` object through which the configuration
  settings specific to the automation can be accessed.
* `name`: A non-empty string indicating the name of the automation. This is
  automatically determined by the name of the python package where the entry 
  point (the `main` function) is located.
* `root_dir`: A `Path` object indicating the location of the automation's
  private "root" folder. This is the sub-folder of `.automation` which is named
  after the automation and serves as its base of operations and the home of its
  log files, persistent data files, temporary working files, and documentation.
* `start_time`: A `datetime.datetime` instance indicating the time at which the
  automation's execution began.
* `subtask_start_notifier`, `subtask_success_notifier`, 
  `subtask_failure_notifier`, `subtask_error_notifier`, `subtask_end_notifier`: 
  Each of these properties is a `Notifier` object which is used to 
  automatically transmit notifications indicating the run-time status of 
  specific subtasks performed by the automation. You will generally have no 
  need to access these directly.
* `task_start_notifier`, `task_success_notifier`, `task_failure_notifier`, 
  `task_error_notifier`, `task_end_notifier`: Each of these properties is a 
  `Notifier` object which is used to automatically transmit notifications 
  indicating the run-time status of specific tasks performed by the automation.
  You will generally have no need to access these directly.
* `testing`: A `bool` indicating whether the automation is being 
  executed in "test mode" -- in which case the automation should not take any 
  actions that could affect the production environment.
* `version`: A non-empty string indicating the version of the automation.
* `workspace`: A `Path` object indicating the location where temporary working
  files should be located for this automation.

### Configuration Files

#### Configuration File Structure

Attila configuration files are structured according to the commonly supported
[INI file format](https://en.wikipedia.org/wiki/INI_file). INI files consist 
of "options" (AKA parameters) organized into named sections. A special DEFAULT
section allows default values to be specified for all sections in a single
location. Each section can then define its own values or fall back to the
defaults. Section names are indicated by placing the name in square brackets, 
`[]`. Option names and values are indicated by placing the name to the left of 
an equal sign, `=`, or a colon `:`, and the value to the right of the 
punctuation. Comments are indicated by a semicolon, `;`, or hash, `#`, and
continue to the end of the line. Multi-line values for an option can be 
specified by indenting the lines after the option name.

Example:

    [Section Name]
    ; Comment
    Option Name 1 = Option Value 1  ; Comment
    # Comment
    Option Name 2: Option Value 2
    Multi-Line Option Name:
        Line 1
        Line 2
        # Comment
        Line 3

#### Configuration File Hierarchy

Attila takes this organization one step further. Configuration files can be
organized into default hierarchies, where requests for configuration settings
are passed on to fallback configuration files if they are not specified in
the primary configuration file. The automation context automatically loads
certain configuration files into the configuration hierarchy accessed through
the `manager` property.

If you have a configuration file located at `~/automation/automation.ini`, 
this will be loaded at initialization time. We will refer to this configuration 
as the *general configuration*.

If your project has a file with extension `.ini` which is named after the 
automation and located in the automation's root folder (e.g. 
`~/.automation/your_automation/your_automation.ini`), this will be loaded at
initialization time, immediately after the general configuration. We will 
refer to this configuration as the *specific configuration*.

You can also specify an additional configuration by passing it in as an
argument to the `@automation` decorator. We will refer to this configuration
as the *override configuration*.

When you request an option or section from the context's `manager` property,
Attila will first consult the override configuration, then the specific
configuration, and finally the general configuration to determine the value
to return, stopping at the first configuration which exists and defines the
requested option or section. If none of the configurations defines the
requested option or section, a `KeyError` will be raised.

#### Interpolation

Attila configuration files also support value interpolation of four different
types: simple interpolation, date/time interpolation, path interpolation, and 
object interpolation.

##### Simple Interpolation

*Simple interpolation* consists of direct value replacement. The syntax
has two forms, `${option}`, and `${section:option}`. With the section name
omitted, the referenced option is assumed to appear in the same section as
the one where it is referenced. When the section name is specified, the 
indicated section will be consulted for the requested option. If the simple
interpolation appears within surrounding text, its string value will be
injected into the text at the location where the simple interpolation 
appears. Multiple simple interpolations can appear within a single option's
value.

##### Date/Time Interpolation

*Date/time interpolation* uses the date/time at which the option is first
requested to interpolate a formatted date string into the option's value.
The syntax is `${datetime_format_string}`, where `datetime_format_string`
is a format string in Python's `datetime` formatting syntax, e.g. `%m/%d/%Y`.
The `datetime` format must contain at least one percent sign, `%` or it will
not be recognized as such. Date/time interpolation follows the same rules as
simple interpolation regarding value injection.

##### Path Interpolation

Unlike simple and date/time interpolation, *path interpolation* allows an
option to return a `Path` object as its value, rather than a simple string.
Path interpolations require the appearance of a URL prefix, `scheme://`, where 
`scheme` is the name of a registered URL scheme, e.g. `ftp`, `https`, or 
`file`. The URL prefix must appear at the beginning of the option's value, and 
the URL must take up the entirety of the option's value.

##### Object Interpolation

Like path interpolation, *object interpolation* allows a parameter to have a
non-string value, and does not support string injection. The syntax for object
interpolation is `@section_name`, where `section_name` is the name of another 
section which determines the type and initialization parameters of a Python 
object. If an option value contains an object interpolation specifier, the 
object interpolation specifier must take up the entirety of the option's value 
with no surrounding text or additional interpolation specifiers. The object 
specified by the indicated section will be returned as the option's value. If 
the same option's value is requested multiple times, the previously returned 
object will be returned again; a new object is not created for subsequent 
requests.

##### Object Loaders

The section referenced by an object interpolation must contain a `Type`
option. This `Type` option indicates the name of the *loader* that is used to 
construct the object represented by the section. When the object 
interpolation's value is first requested, control will be handed off to to the 
indicated loader to construct the object on the configuration manager's behalf.
Subsequent requests for the section's corresponding object will return that
same object again. This allows for the parameterization and lazy construction 
of complex object structures which make multiple references to the same 
underlying objects.
 
Loaders must be pre-registered with the configuration management system before 
they are used to load the options or sections that refer to them. Loaders can
be registered at install-time via a plugin mechanism, or at run-time via the
`@config_loader` decorator. To register a function or class via the plugin
mechanism, your package should use the `attila.config_loader` entry point. 
(See [this StackOverflow question](
https://stackoverflow.com/questions/774824/explain-python-entry-points)
for an explanation of entry points.)

A loader can be defined as either a simple function, or as a class which 
inherits from the `Configurable` abstract base class. If your loader is
a function, it should expect a single argument: The name of the section
to be loaded. (Note that when requesting the value of an option from code, a 
loader can be selected by passing its name to the configuration manager. In 
this case, the entire original string value of the option, which may not be
a section name, is passed to the loader instead.) If your loader is a class
which inherits from `Configurable`, your class must implement the 
`load_config_section` method, which is passed the configuration manager and
the section name to be loaded as its arguments. Additionally, your class can 
implement the `load_config_value` method, which handles cases where the loader
is specifically requested by name from the calling code when loading an option.
If you do not implement `load_config_value`, your loader can only be used to
load sections, not options.

## Event Handling and Notifications

Attila offers a built-in mechanism for configurable event notifications via a
standardized interface, allowing file and database logging, emails, other 
message types, and even arbitrary function calls to be swapped 
interchangeably with no changes to the code. The standardized interface for 
event notifications is the `Notifier` abstract base class. Attila provides 
several predefined notifier types:

* `CallbackNotifier` passes the arguments to an arbitrary Python callable 
  instance, e.g. a function or method.
* `CompositeNotifier` chains multiple notifiers together into a single notifier
  instance.
* `EmailNotifier` constructs and sends an email by interpolating arguments into
  a template.
* `FileNotifier` writes notifications to a file.
* `LogNotifier` sends notifications to Python's built-in logging system.
* `MutexNotifier` wraps another notifier and ensures calls are serialized in a
   multi-threaded environment.
* `NullNotifier` ignores all notifications.
* `SQLNotifier` inserts or updates rows in a SQL table.

Additional notifier types can be implemented by subclassing the `Notifier` 
class. All of the notifier types that Attila provides are registered as 
configuration loaders, meaning they can be configured via parameters and loaded 
using the configuration manager.

## Tasks and Subtasks

Attila provides specialized context managers, `task` and `subtask`, which hook 
into the notification system to allow the configuration of task status 
reporting. Task and subtask contexts send notifications upon entry, exit, 
error, and success/failure of the code appearing within their context. Each of
these notification types is sent to a separately defined notifier determined by
the configuration manager, allowing them to be ignored, redirected, or 
otherwise modified in a way that is completely transparent to the source code.
The task and subtask context managers are designed to not only simplify the
configuration and management of task-related notifications, but to also serve
the dual purpose of making code more self-documenting.

Below is an example use case of the `task` context manager. Upon entering the
`with` block, the `task_start_notifier`, determined by the configuration 
manager, is called. If/when the task is explicitly marked as successful (or 
failed), the `task_success_notifier` (or `task_failure_notifier`) is 
immediately called. If an unhandled exception occurs before the task is marked 
as successful or failed, it is automatically marked as failed. Regardless of
whether the task was previously marked as successful or failed, an unhandled
exception always results in a call to `task_error_notifier`. If the `with`
block is exited without an unhandled exception, the task is marked as
successful (unless it has already been marked successful or failed) and the
`task_end_notifier` is then called.

    with task("Confirming order.") as order_confirmation:
        # Do required stuff.
        if condition:
            # Mark the task as successful:
            order_confirmation.success("Order confirmed!")
            # Do optional stuff.

Subtasks work identically to tasks, except they have separately configured
notifiers.

## Security

Attila provides security management functionality which is fully integrated
with the configuration system. Support for encrypted password storage, both
in the file system and in a remote database, is built in.

### Password Database Configuration

In order to use the password database integration, the `Password DB Connector`
and `Master Password Path` options must be set in the `Security` section of the
`automation.ini` configuration file. Here we have an example configuration 
which utilizes an ADODB connection to a SQL Server instance using a trusted
connection:

    [Security]
    Password DB Connector: @Password Database Connector
    Master Password Path: ${Environment:Shared Data}/password.dat
    
    [Password Database Connector]
    Type:     ADODBConnector
    Server:   123.456.789.10
    Database: SecurityDB
    Driver:   SQL Server
    Dialect:  T-SQL
    Trusted:  True

The master password, stored in a locally encrypted file, is used to encrypt
and decrypt the passwords stored in the database. The database must contain
a table named `AutomationPasswords` with the following fields:

* `System`: A varchar field containing the name of the system or domain.
* `UserName`: A varchar field containing the user name.
* `Password`: A varchar or blob field wide enough to contain the password
  plus the "salt" -- 2,048 random bytes encrypted along with the password to 
  prevent cracking attempts.
* `Valid`: A bit or Boolean field which indicates whether the password is
  currently considered valid. This indicator can be cleared upon a failed login
  attempt to prevent multiple attempts which might lock out the user.
  
### Credential Configuration

Often your automations will need to connect to systems that require password
authentication, particularly in the cases of database connections and remote 
file systems. Attila provides the `Credential` configuration loader for 
securely configuring domain/user/password triples. To help prevent accidental 
security leaks, e.g. through accidental source control commits, all loaders 
provided by Attila which utilize credentials only support passwords stored in 
encrypted form. 

#### URL Schemes
 
URL schemes that permit embedded password authentication typically take the
form, `scheme://user@password:domain`. The URL schemes implemented in Attila
require the `@password` portion of these URLs to be omitted. When the `Path`
is loaded from the configuration file, the appropriate password is
automatically looked up in the password database, decrypted, and interpolated
into the URL. The password should be stored in the database using the value 
`domain/scheme` as the domain and `user` as the user name. For example, for
the URL `sftp://greg@Pa$$w0rd/ftp.server`, the password should be stored using
`ftp.server/sftp` as the domain and `greg` as the user name.

## Convenience Functions

Attila provides several utility functions which are commonly useful in writing
automations and help prevent code bloat. Most of the functions described below
accept additional arguments to fine-tune their behavior. Check out their doc 
strings for more detailed information.

### attila.exceptions

#### Functions 

* `verify_type(obj, typ)`: Check that the object has the expected type. If not,
  raise a `TypeError`.

### attila.processes

#### Functions

* `process_exists(pid, name)`: Return a Boolean indicating whether a process 
  exists.
* `count_processes(pid, name)`: Count the number of active processes. If a 
  process ID or process name is provided, count only processes that match the 
  requirements.
* `get_pids(name)`: Return a list of process IDs of active processes with the
  given name.
* `get_name(pid)`: Return the name of the process if it exists, or the default 
  otherwise.
* `get_command_line(pid)`: Return the command line of the process.
* `get_parent_pid(pid)`: Return the process ID of the parent process.
* `get_child_pids(pid)`: Return the process IDs of the child processes in a 
   list.
* `kill_process(pid)`: Kill a specific process.
* `kill_process_family(pid)`: Kill a specific process and all descendant 
   processes.
* `capture_process(command)`: Call the command and capture its return value. 
  Watch for a unique process to be created by the command, and capture its PID. 
  If a unique new process could not be identified, raise an exception. This is
  useful for ensuring process cleanup for commands that generate new processes
  in unreliable environments, particularly COM automation.

### attila.progress

#### Functions

* `progress(iterable)`: Automatically log the progress made through an iterable
  sequence. This is useful for long-running `for` loops; just wrap the sequence
  you're iterating over in a call to the `progress` function to log the `for` 
  loop's progress.

### attila.strings

#### Functions

* `get_type_name(type_obj)`: Get the name of a type.
* `parse_bool(string)`: Parse a `bool` from a string.
* `parse_char(string)`: Parse a single character from a string. The string can 
  be anything that would be interpreted as a character within a string literal, 
  i.e. the letter a or the escape sequence \t, or it can be an integer ordinal 
  representing a character. If an actual digit character is desired, it must be 
  quoted in the string value.
* `parse_int(string)`: Parse an integer from a string.
* `parse_number(string)`: Parse a number from a string. Returns either an 
  integer or a float.
* `format_currency(amount)`: Format a decimal amount as a dollar amount string.
* `format_ordinal(number)`: Given an integer, return the corresponding ordinal 
  ('1st', '2nd', etc.).
* `glob_to_regex(pattern)`: Convert a glob-style pattern (e.g. `*.txt`)to a 
  compiled regular expression.
* `glob_match(pattern, string)`: Return a Boolean indicating whether the string 
  is matched by the glob-style pattern.
* `format_english_list(items)`: Make an English-style list (e.g. "a, b, and c") 
  from a list of items.
* `date_mask_to_format(mask)`: Convert a date mask (e.g. `YYYY-MM-DD`) to a 
  date format (e.g. `%Y-%m-%d`).
* `parse_datetime(string)`: Parse a date/time string, returning a 
  `datetime.datetime` instance.
* `parse_date(string)`: Parse a date string, returning a `datetime.date` 
  instance.
* `parse_timedelta(string)`: Parse a timedelta from a string.
* `split_port(ip_port)`: Split an IP:port pair.
* `parse_log_level(string)`: Parse a log level, e.g. INFO, WARNING, etc.
* `to_list_of_strings(items)`: Parse a delimited string into a list of 
  non-empty strings.
* `to_list_of_lines(string)`: Parse a newline-delimited string into a list of
  non-empty strings.

#### Classes

* `DateTimeParser`: A generic parser for date/time strings.
* `USDateTimeParser`: A generic parser for date/time values expressed in common 
  formats used in the US.

### attila.threads

#### Functions

* `async(function, *args, **kwargs)`: Call a function asynchronously. The 
  function runs in a separate background thread while the current execution
  flow continues uninterrupted. The returned object can be checked to find
  out when the called function has returned and what its return value was, or
  joined like an ordinary thread.

#### Context Managers

* `mutex(name)`: Hold a mutex (a unique, system-wide, named resource lock) 
  while executing a block of code. Only one process or thread can hold a
  given mutex at a time. If another process or thread tries to acquire the
  mutex, it will wait for the one already holding it to release it first. This
  is an easy way to ensure that a particular resource (often a file) is only
  accessed by one process or thread at a time, to avoid race conditions.
* `semaphore(name, max_count)`: Hold a semaphore (a system-wide named resource
  counter) while executing a block of code. A semaphore is just like a mutex,
  except that up to `max_count` processes or threads can hold the semaphore at
  one time.

### attila.utility

#### Functions

* `first(items)`: Return the first item from a sequence. If the item sequence 
  does not contain at least one value, raise an exception.
* `last(items)`: Return the last item from a sequence. If the item sequence 
  does not contain at least one value, raise an exception.
* `only(items)`: Return the only item from a sequence. If the item sequence 
  does not contain exactly one value, raise an exception.
* `distinct(items)`: Return a list of the items in the same order as they first 
  appear, except that later duplicates of the same value are removed. Items in 
  the sequence must be hashable, or, if a key is provided, the return values of 
  the key must be hashable.
* `wait_for(condition)`: Repeatedly sleep until the condition (a lambda 
  expression or function which accepts zero arguments) returns `True`.
* `wait_for_keypress()`: Wait until the user presses a key on the keyboard.

#### Decorators

* `@once`: The function this decorator is applied to becomes callable only 
  once. Subsequent calls to the function return the same value as the original
  call, regardless of the argument values provided.

### attila.windows

#### Functions

* `set_title(title)`: Set the title for the console window of the script.
* `window_exists(title)`: Return a Boolean value indicating whether a window 
  with the given title exists.
* `force_close_windows(title_pattern)`: Force-close all windows with a title 
  matching the provided pattern.

## Packaging and Installation

TODO: Go over how to package and distribute Attila automations, and the
      special functionality provided in attila.installation.
