import win32con
import win32security


from .passwords import get_password, get_master_password


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

    DEFAULT_USER = 'ERNAMAUTO'
    DEFAULT_DOMAIN = 'ERICSSON'
    PASSWORD_SYSTEM = 'Windows'
    USE_MASTER_PASSWORD = True

    _sustained = {}

    @classmethod
    def sustained(cls, user_name=None, password=None, domain=None):
        """
        Login as the given user (ERNAMAUTO by default) and leave it logged in.

        :param user_name: The account's user name.
        :param password: The account's password.
        :param domain: The account's domain.
        """

        if user_name is None:
            user_name = cls.DEFAULT_USER

        if domain is None:
            domain = cls.DEFAULT_DOMAIN

        key = (user_name, domain)

        if key not in cls._sustained:
            imp = cls(user_name, password, domain)
            imp.impersonate()
            cls._sustained[key] = imp

    def __init__(self, user_name=None, password=None, domain=None):
        self.handle = None

        if user_name is None:
            user_name = self.DEFAULT_USER

        if password is None:
            # noinspection PyBroadException
            try:
                password = get_password(self.PASSWORD_SYSTEM, user_name, False)
            except Exception:
                if user_name == self.DEFAULT_USER and self.USE_MASTER_PASSWORD:
                    password = get_master_password(False)
                else:
                    raise

        if domain is None:
            domain = self.DEFAULT_DOMAIN

        self.domain = domain
        self.user_name = user_name
        self.password = password

    def __del__(self):
        """
        Called automatically by the garbage collector just before the object is destroyed.
        """

        self.logout()

    def login(self):
        """
        Log in as the user. This just validates the credentials with the OS, but doesn't actually
        use them.
        """

        if self.handle is None:
            self.handle = win32security.LogonUser(
                self.user_name,
                self.domain,
                self.password,
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