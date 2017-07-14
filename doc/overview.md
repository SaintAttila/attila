
# The Big Idea


## What is an "automation"?

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

## What is Attila?

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


# Automation Environment

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


# Abstraction Layer

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


# Getting Started


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

TODO: Explain how passwords are managed securely, and how to properly
      utilize the security submodule for password safety and secure
      data storage.

## Convenience Functions

TODO: Go over the contents of attila.utility and attila.progress, and
      the verify_type function.

## Packaging and Installation

TODO: Go over how to package and distribute Attila automations, and the
      special functionality provided in attila.installation.


# Structure of the Attila Codebase

TODO: Go over the structure of the library - how things are arranged and
      why, and where to find what you're looking for.
