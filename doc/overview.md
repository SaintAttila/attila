
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


## Configuration Files

TODO: Explain how configuration files work, and how to use them to best
      effect. Don't forget to explain writing your own configuration
      loaders.

## Tasks and Subtasks

TODO: Explain how tasks & subtasks work, how they can be used to make
      code more self-documenting, and how they interface with the
      configuration files.

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
