Placement of related data files
===============================


Things to consider:

* Global/shared parameters
* Parameter files
* Log files
* Data folder (Files installed along with the automation containing data that won't fit in parameter files.) 
* Working folder (Files created by the automation after installation.)
* Documentation
* Differences in behavior between main module or package versus sub-modules and -packages. 


The "home" folder, represented as `~`, on Windows is `C:\Users\ERNAMAUTO\`. The "proper" place to put data on Windows is
in `~\AppData\Local\<company name>\<program name>\`. Another common standard, ported from Linux, is to use
`~\.<program name>\`. Using `AppData` has the disadvantage that `AppData` is a hidden folder. It also means traversing a
longer path to find the appropriate location. And finally, it expects a company name, which doesn't make much sense
when deploying in-house automation software. Using `.<program name>` has the disadvantage of not being proper Windows
etiquette. In this case, I think etiquette can suck it. (How rude!)


We will use `~\.automation\` as our root folder. Global/shared parameters will go in a file named `automation.ini` in
that folder. Parameter files will be named after the full package namespace, i.e. the name you would use to import the 
package, including dots for nested packages, with the extension `.ini`, and will be placed directly in the 
`~\.automation\` folder: `~\.automation\<my_package.name>.ini`. Logs will be written to `~\.automation\logs\<package>\` 
and will be named after the *root* package namespace, followed by an underscore, followed by the date in format 
`YYYYMMDD`, with extension `.log`: `~\.automation\logs\<my_package>_<YYYYMMDD>.log`. The root working folder for the 
script will default to `~\.automation\workspace\<my_package>\`. Documentation will be placed in 
`~\.automation\docs\<my_package>\`. Non-parameter install data will be placed in `~\.automation\data\<my_package>\`.


Let's do a specific example. Assume we have two automations installed named `my_module` and `my_package`, where
`my_package` has a sub-module named `name`. We have associated documentation for these two automations named 
`module.docx` and `package.txt`, respectively. Each of them has been run twice, once on 3/2/2016 and once on 3/3/2016,
generating log files each time. The `my_package` automation also keeps persistent state information between runs in a
file named `state.txt`. Suppose also that `my_package.name` has its own, separate configuration file, and has an 
associated data file, `stuff.dat`, installed alongside the automation. Here's the full folder structure:

* `~` (`C:\Users\ERNAMAUTO\`)
    * `.automation`
        * `data`
            * `my_package`
                * _`stuff.dat`_
        * `docs`
            * `my_module`
                * _`module.docx`_
            * `my_package`
                * _`package.txt`_
        * `logs`
            * `my_module`
                * _`my_module_20160302.log`_
                * _`my_module_20160303.log`_
            * `my_package`
                * _`my_package_20160302.log`_
                * _`my_package_20160303.log`_
        * `workspace`
            * `my_module`
            * `my_package`
                * _`state.txt`_
        * _`automation.ini`_ 
        * _`my_module.ini`_
        * _`my_package.ini`_
        * _`my_package.name.ini`_


This folder structure applies only to new-style automations, i.e. those that are packaged into wheel files (`.whl`) and
installed with `pip`. The old-style automations, installed with a manual folder copy/paste, will still follow the old
structure, keeping their logs and parameters in folders next to the source files and using the script's path as the
working folder. That means we'll need to set some sort of compatibility flag or perhaps look at the path of the
importing module when we determine which behavior to use. The second possibility seems like the more reliable mechanism.
It would be fairly straight-forward to look at the caller's path and determine if `site-packages` appears in it.


Old-style folder structure:

* `<script name>` (install path outside of `site-packages`, also serving as the working path)
    * `logs`
        * `<script name>_<YYYYMMDD>.log`
    * `parameters`
        * `<script name>_Parameters.txt`
        * `<optional data file(s)>`
    * `<script name>.py`


Logic for loading script parameters:

* If BaseParameters is being used:
    * Attempt to load from `<script folder>\parameters\<script name>_Parameters.txt`.
* Otherwise:
    * If package is in `site-packages`:
        * Attempt to load from `~\.automation\<package name>.ini`.
    * Attempt to load from `<script path>\<script name>.ini`.


Logic for loading global parameters:

* If BaseParameters is being used:
    * Attempt to load from `<python path>\Lib\parameters\baseParams_Parameters.txt`.
* Otherwise:
    * Attempt to load from `~\.automation\automation.ini`.
    * Attempt to load from `<site-packages>\base\automation.ini`.


Logic for determining log path:

* If script is in `site-packages`:
    * Log to `~\.automation\logs\<script name>\<script name>_<YYYYMMDD>.log`.
* Otherwise:
    * Log to `<script folder>\logs\<script name>_<YYYYMMDD>.log`.


* Logic for setting working directory:
    * If script is in `site-packages`:
        * Change to `~\.automation\workspace\<script name>\`, creating folder if necessary.
    * Otherwise:
        * Set to script path.
    * Note the working directory in the log.


When `attila` comes out, we will specify the location of `.automation` in a `attila.ini` parameter file, which will be
located through the traditional search paths for Python package parameters. Then, for shops that don't care for our
settings, they will have the ability to change them. Note that `attila.ini` is distinct from `automation.ini`. The
`attila.ini` file controls the behavior of the `attila` library, whereas `automation.ini` provides shared parameters for
all automations built on top of `attila`. In other words, anything shared globally that is used by `attila` itself goes 
in `attila.ini`, whereas anything shared globally that is *not* used by `attila` goes in `automation.ini`.


