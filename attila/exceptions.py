"""
attila.exceptions
=================

Exception definitions for attila.
"""


class AttilaException(Exception):
    """Base class for all exceptions defined by attila."""


class ConfigurationError(AttilaException):
    """Error in configuration."""


class InvalidConfigurationError(ConfigurationError):
    """The configuration is invalid."""


class ConfigSectionNotFoundError(KeyError, ConfigurationError):
    """The config section could not be found."""


class ConfigParameterNotFoundError(KeyError, ConfigurationError):
    """The config parameter could not be found."""


class ObjectNotConfiguredError(ConfigurationError):
    """The object has not been configured."""


class ObjectNotReconfigurableError(ConfigurationError):
    """The object cannot be reconfigured."""


class NoConfigurableInstanceTypeError(NotImplementedError, ConfigurationError):
    """The configuration does not support configured instances."""


class PathError(OSError, AttilaException):
    """Base class for path-related exceptions."""


class DirectoryNotEmptyError(PathError):
    """The operation requires the directory to be empty, and it is not."""


class InvalidPathError(PathError):
    """The path is incorrect."""


class NoDefaultFSConnectionError(PathError):
    """No default file system connection has been provided."""


class SecurityError(AttilaException):
    """Security-related error."""


class CryptographyError(SecurityError):
    """Error during encryption or decryption."""


class EncryptionError(CryptographyError):
    """Error during encryption."""


class DecryptionError(CryptographyError):
    """Error during decryption."""


class PasswordError(SecurityError):
    """Password-related error."""


class PasswordRequiredError(KeyError, PasswordError):
    """Password is unknown/expired."""


class BadPasswordError(ValueError, PasswordError):
    """Not a valid password."""


class PluginError(AttilaException):
    """Plugin-related error."""


class PluginExistsError(KeyError, PluginError):
    """The plugin already exists."""


class InvalidPluginError(ValueError, PluginError):
    """The plugin is invalid."""


class PluginNotFoundError(KeyError, PluginError):
    """The plugin does not exist or could not be found."""


class OperationNotSupportedError(NotImplementedError, AttilaException):
    """The requested operation is not available for this object."""


class ConnectionStatusError(ConnectionError, AttilaException):
    """Error related to the status of a connection."""


class ConnectionOpenError(ConnectionStatusError):
    """The connection is open."""


class ConnectionNotOpenError(ConnectionStatusError):
    """The connection is closed."""


class ConnectionReopenError(ConnectionStatusError):
    """The connection cannot be reopened."""


class PropertyError(ValueError, AttilaException):
    """Base class for property-related errors."""


class PropertyAlreadySetError(PropertyError):
    """The property has already be set and cannot be changed."""


class PropertyNotSetError(PropertyError):
    """The property has not been set."""


def verify_type(obj, typ, *, non_empty=False, allow_none=False):
    """
    Verify that the object has the given type. If not, raise an appropriate exception.

    :param obj: The object to check.
    :param typ: The expected type (or a tuple of types).
    :param non_empty: If True, require the object to evaluate as True in a boolean context. (Default
        False)
    :param allow_none: If True, allow the object to be None. (Default False)
    """
    if allow_none and obj is None:
        return
    if not isinstance(obj, typ):
        raise TypeError(type(obj), typ)
    if non_empty and not obj:
        raise ValueError(obj)


def verify_callable(obj, *, allow_none=False):
    """
    Verify that the object is callable. If not, raise an appropriate exception.
    :param obj: The object to check.
    :param allow_none: If True, allow the object to be None. (Default False)
    """
    if allow_none and obj is None:
        return
    if not callable(obj):
        raise TypeError(callable, obj)
