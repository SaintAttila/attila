### Starting Point: Automation Hooks

Required Hooks:

* Error handling
* Startup
* Shutdown


How do we specify hooks in a config file, so we can write a new script without
having to worry about setup, but we also keep attila setup to a minimum?


Possible Solutions:

* Provide a subclass of automation_environment in another library.
* Use direct code references in the config file.
* Use a registry, which other libraries can use to setup hooks when loaded.
* Use a *persistent* registry, which other libraries can use to setup hooks when
  installed.
* A plugins folder where_clause Python scripts can be dropped to create hooks.
* Make hooks be installable sub-packages.


The problem here is that we have multiple different scopes for writing client
code: Shared systems-level functionality used across all automations, and the
automations themselves. We want the automation developer to be able to just
write an automation and not worry about the environment it is used in, but we
want the systems developer to be able to push changes to the environment for all
automations without having to modify the attila library itself. There are two
different types of systems-level development, though: functionality, and policy.
For functionality development, ordinary libraries are perfectly sufficient. The
systems developer simply packages up the libraries, and the automation developer
imports and uses them. But for policy development, there has to be a way for the
systems dev to modify the environment without the automation devs' involvement.


Automation development scopes:

* Framework Level: attila
* Systems Level: shop-specific policy hooks
* Library Level: ordinary shop-specific libraries
* Automation Level: individual automations


We need to provide a mechanism for the distribution of shop-specific automation 
policies alongside the attila framework. But this opens a new can of worms: Do
we permit multiple policies to coexist on a single server? If so, how does 
attila know which policies are in effect for a given automation? And won't we
then have to support multiple different policy profiles, rather than the single
profile we assume, where_clause automations are housed in ~/.automation and we use the
unique automation.ini global configuration? Before design continues, we need to
determine precisely what it is that attila hopes to achieve. What are the 
design goals? What are the assumptions? Do we only support one shop per server,
or do we assume that multiple shops can use a single server for their 
automations? I am leaning strongly towards single-shop servers, but if we go
down that road, it's not an easily reversed decision.

Most companies would flatly reject the possibility of another company accessing
their data, so the use cases where_clause two competing companies share a server is
non-existent; they would at the least setup is_distinct virtual environments to 
keep their data private. In another scenario, imagine an end-user installing
automation software from two different shops, both based on attila, to process
the user's data. This is an unlikely scenario, and we can address it by simply
providing the ability for these shops to build libraries on top of attila which
redirect configuration loading to locations specific to each library. Such a
change would not be a total revamp of attila itself even if this sort of 
support were not built in from the ground up, as we can hide the changes from
the more typical user through the intelligent application of default value_list.
This leaves only one other major use case: A single shop per server.


### Targeted Use Case: One Shop Per Server

Keeping in mind that we need to provide override hooks for library developers
that implement on top of attila, we can now focus in on our primary use case,
which looks like this:

* A dev shop chooses attila as an automation framework.
* The shop installs attila on each of its automation servers.
* The shop's system devs create a single cohesive automation policy for 
  installation alongside attila on each of its automation servers.
* The shop's automation devs create automations which are ignorant of the 
  automation policy and simply perform their intended tasks.


Our assumptions are now:

* There will be one or more automation servers, owned and managed by the same 
  dev shop.
* There will be multiple automations running on each automation server.
* All automations on a server will be governed by a single automation policy.
* The automation policy will be developed by the dev shop.
* Automations should be ignorant, and not in control, of the choice of 
  automation policy.


Thus the design goal of attila becomes:

* Simplify/automate the creation, management, and distribution of automations 
  and automation policies at a per-server level.


There are two levels to this goal: coding, and automation. We want to make it
as easy as possible to create, manage, and distribute theses systems, and that
means that we should automate these steps to the maximum extent possible. That
means we should provide:

* A mechanism for creating a new policy or automation template as a project on 
  the dev's machine.
* A mechanism for packaging a new policy or automation for distribution.
* A mechanism for remotely installing a policy or automation on a particular
  server or set of servers.
* A mechanism for remotely observing and controlling the execution and 
  scheduling of automations on a particular server or set of servers. 


### What form does the automation policy take?

First, let's determine what an automation policy consists of. An automation
policy is a collection of shop-specific parameter settings and code that 
together determine the common behaviors for all automations on a server. The 
policy has to have some mechanism for hooking into attila in an unobtrusive
manner which doesn't require the individual automations to know or care which
policy is in effect. At this point we have returned to the starting point. How
does the policy hook into attila so the automations don't have to be aware of 
it? Let's look at some specific possible solutions and do a deeper analysis of
each.


#### Solution #1: Installable Plugins as Submodules

In this approach, we have a specially-designated subpackage, attila.plugins,
in which plugins are installed as submodules.


Pros:

* Plugins can be independently installed and removed.
* The installation, selection, and loading of plugins is completely invisible 
  to the automations.


Cons:

* Plugin loading order may not be well-defined. Mitigation: Provide a mechanism 
  in the configuration files or during installation to control loading order.
* No obvious way to push a group of plugins at the same time. Mitigation:
  Automate the installation of plugins.
* Different settings for a particular server require repackaging and 
  installation of the plugin. Mitigation: Optional config files for each 
  plugin, rather than only at the attila and automation levels.
  

#### Solution #2: Installable Monolithic Policy Plugin

In this approach, a uniquely named (or placed) shop-specific package is 
installed which attila defers to on policy-related decisions when it is 
present.


Pros:

* Completely customizable with shop-specific code, including the ability to 
  support other solutions described here.
* Invisible to automations.


Cons:

* Shop must write a specialized module.
* Different per-server settings require either a different package to be 
  installed, or the same package to support all possible mechanisms.
  

#### Solution #3: Config with Python Hooks

In this approach, we specify hooks into Python code directly in the 
automation.ini config file.


Pros:

* Fully customizable.
* Invisible to automations.
* Specialized code is entirely optional.
* Fully compatible with Solution #1 above, with built-in mitigation for all 
  cons to that solution except for the plugin installation.


Cons:

* Issues related to importing and scoping when locating the functions to call.
* Injecting code into parameters, which is distasteful to some.


#### Solution #4: Notification-Based Policy

In this approach, instead of installing plugins or other specialized Python 
code, we simply provide the ability to generate arbitrary notifications at
significant moments, and allow the handling of those notifications at the 
receiving end.


Pros:

* Since additional notification types are planned to be plugins anyway, no
  additional mechanisms need to be provided besides loading of notification
  parameters and triggering of notifications at callback points.
* Fully customizable.
* Invisible to automations.
* Depending on the existence of local code-triggering channels/notifications,
  can encompass all other solutions.
* Easily extensible.
* Small initial code commitment.


Cons:

* Notifications are one-way. Mitigation: Add a mechanism for notification 
  receipts/replies.
* If the server is offline, may cause additional problems that would not
  occur for a locally-handled policy. Mitigation: Channels and notification
  types that trigger local Python code.
