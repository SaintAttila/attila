"""
attila.security.impersonation
=============================

Implements the impersonation class for temporarily or semi-permanently logging in with different
credentials.
"""


import win32con
import win32security


from ..configurations import get_automation_config_loader
from ..exceptions import verify_type

from .credentials import Credential


class impersonation:
    """
    This class allows a script to log in as another user temporarily. It works as a context manager,
    so the typical usage will look like this:

        with impersonation(user_name, password):
            # Do stuff that requires us to be logged in as user_name

    If you want to stay logged in as another user for the duration of your function's execution, do
    this:

        imp = impersonation(user_name, password)
        imp.impersonate()

    This will leave you impersonating user_name until "impersonation" goes out of scope and gets
    garbage-collected, or until you call imp.revert() or imp.logout().

    If you want to stay logged in until your script exits, without having to keep a reference to an
    impersonation instance, do this:

        impersonation.Sustained(user_name, password)
    """

    _sustained = {}

    @classmethod
    def sustained(cls, credential=None):
        """
        Login as the given user and leave it logged in.

        :param credential: The account credential.
        """

        if credential is None:
            config_loader = get_automation_config_loader()
            credential = \
                config_loader.load_option('Security', 'Default Login Credential', Credential)

        verify_type(credential, Credential, non_empty=True)
        assert isinstance(credential, Credential)
        assert credential.is_complete

        key = (credential.user, credential.domain)

        if key not in cls._sustained:
            imp = cls(credential)
            imp.impersonate()
            cls._sustained[key] = imp

    def __init__(self, credential=None):
        self.handle = None

        if credential is None:
            config_loader = get_automation_config_loader()
            credential = \
                config_loader.load_option('Security', 'Default Login Credential', Credential)

        verify_type(credential, Credential, non_empty=True)
        assert isinstance(credential, Credential)
        assert credential.is_complete

        self._credential = credential

    def __del__(self):
        """
        Called automatically by the garbage collector just before the object is destroyed.
        """
        self.logout()

    @property
    def credential(self):
        """The Credential instance used to log in."""
        return self._credential

    def login(self):
        """
        Log in as the user. This just validates the credentials with the OS, but doesn't actually
        use them.
        """
        if self.handle is None:
            self.handle = win32security.LogonUser(
                self.credential.user,
                self.credential.domain,
                self.credential.password,
                win32con.LOGON32_LOGON_INTERACTIVE,
                win32con.LOGON32_PROVIDER_DEFAULT
            )

    def logout(self):
        """
        Log out of the user's account. If currently impersonating the user, impersonation is also
        ended.
        """
        if self.handle is not None:
            win32security.RevertToSelf()
            self.handle.Close()
            self.handle = None

    def impersonate(self):
        """
        Begin using the credentials. Logs in first if necessary.
        """
        self.login()
        win32security.ImpersonateLoggedOnUser(self.handle)

    def revert(self):
        """
        Stop using the credentials. The user is left logged in, which can speed up later
        impersonations with the same credentials.
        """
        if self.handle is not None:
            win32security.RevertToSelf()

    def __enter__(self):
        """
        Called automatically upon entering a with block.
        """
        self.impersonate()

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Called automatically upon leaving a with block, whether due to normal execution or an error.
        """
        self.revert()
        return False  # Do not suppress errors
