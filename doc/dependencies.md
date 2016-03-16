adodb:
    pywin32
    attila.security (after module load)

context:
    -

error_handling:
    -

emails:
    attila.env
    attila.notifications
    attila.strings

env:
    -
    
error_handling:
    -

files:
    Windows DLLs (optional)

notifications:
    -

processes:
    pywin32
    attila.utility

progress:
    -

resources:
    wmi
    attila.utility

security:
    pywin32 (optional)
    cryptography
    Windows DLLs
    attila.adodb
    attila.param

smtp:
    attila.utility
    attila.param

strings:
    -

threads:
    pywin32

utility:
    -

windows:
    pywin32
    attila.processes
    attila.strings
    attila.threads


