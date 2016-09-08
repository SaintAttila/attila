
# The Big Idea

Before going into what Attila is and does, it's important to understand 
the programming paradigm it's intended for. Attila was built to 
facilitate the development and maintenance of _automations_. What's an 
automation? An automation is a piece of software specifically designed 
to run autonomously, without supervision or intervention, in unobserved 
environments like remote servers, or PCs and laptops during off hours.
Automations differ from more familiar forms of software in that they
seldom provide meaningful user interfaces - typically taking the form of
a simple window with scrolling log or status messages - and they are
typically controlled through a task scheduler, command prompts, and/or
parameter files. In this respect, they closely resemble OS services, but
they differ from services in that they have specific jobs they 
accomplish (e.g. generating reports, sending emails, updating database 
tables, or processing regularly generated files) rather than simply
providing background support for other software.

With the concept of automation programming in mind, Attila's purpose
becomes much easier to express: Attila is not only an automation 
library; it's a _framework_ for building and installing automations. The 
primary goal underlying all of Attila's design is that it should be as 
easy as possible to build, install, and maintain automations. A good 
framework should get out of your way so you can get down to business; it 
should be invisible except when you need it to do something for you. 
With this in mind, Attila does its best to minimize the required 
boilerplate code, and to streamline the most common tasks that are 
required of an automation. These include interactions with data stores 
such as databases and files, generation of notifications like emails and 
log messages, dealing with parameter file configurations, securely 
storing and accessing system login credentials, interacting with other 
threads, processes, and windows, and installing and updating 
automations.


# Automation Environment

Attila assumes a particular model of development: A single development 
shop, operating in a privately controlled, multi-server environment, 
with its own unique standards for how the automations it develops and 
manages should behave. With this in mind, Attila supports the 
configuration of the shared automation environment at the system account 
level on each server. The per-account configuration takes the form of an 
automation.ini file installed in the ~/.automation folder, where ~ is
used to represent the account's "home" folder. (Linux users will find
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

TODO: Explain for dev shops adopting Attila, in particular how to 
      install Attila and configure the automation environment, and how
      the .automation folder is organized.

## Writing Your First Automation

TODO: Explain how to put together an automation for the Attila framework
      once Attila is installed and the environment is configured.

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
