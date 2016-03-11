import sys


def error_response(response):
    """
    Decorator used to indicate a default error response function.

    Example Usage:
        from attila.error_handling import error_response, ErrorHandler

        @error_response
        def send_error_email(exc_type, exc_val, exc_tb):
            ...

        @error_response
        def log_error_event(exc_type, exc_val, exc_tb):
            ...

        with ErrorHandler.default():
            1/0  # Will cause send_error_email() and log_error_event() to be called.

    :param response: The function to be added as a default error response.
    :return: The original function.
    """

    assert callable(response)
    ErrorHandler.default().add(response)
    return response


class ErrorHandler:
    """
    Example Usage:
        from attila.error_handling import error_response, ErrorHandler

        @error_response
        def send_error_email(exc_type, exc_val, exc_tb):
            ...

        @error_response
        def log_error_event(exc_type, exc_val, exc_tb):
            ...

        with ErrorHandler.default():
            1/0  # Will cause send_error_email() and log_error_event() to be called.
    """

    _default = None

    @classmethod
    def default(cls):
        if cls._default is None:
            cls._default = cls()
        return cls._default

    def __init__(self):
        self._responses = []

    def add(self, response):
        if response in self._responses:
            self._responses.remove(response)
        self._responses.append(response)

    def discard(self, response):
        if response in self._responses:
            self._responses.remove(response)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for response in self._responses:
            try:
                if response(exc_type, exc_val, exc_tb):
                    break  # A True return value indicates the error was handled.
            except Exception:
                # Replace the error info with the new error, which will include the old error's info, too.
                exc_type, exc_val, exc_tb = sys.exc_info()
        return False  # Do not suppress exceptions.
