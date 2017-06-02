"""
Temporary files with automatic cleanup
"""


import io


from ..abc.files import Path


__author__ = 'Aaron Hosford'
__all__ = [
    'TempFile',
]


class TempFile:
    """
    Wrapper class for temporary files which automatically deletes them when they are closed.
    """

    def __init__(self, path, *args, **kwargs):
        self._path = path
        self._file_obj = path.open(*args, **kwargs)
        self._modified = False
        assert isinstance(path, Path)
        assert path.exists

    def __del__(self):
        self.close()

    @property
    def path(self):
        """The path to the temp file."""
        return self._path

    @property
    def closed(self):
        """Whether the file has been closed."""
        return self._file_obj is None or self._file_obj.closed

    @property
    def encoding(self):
        """The encoding of the file."""
        return self._file_obj.encoding

    @property
    def name(self):
        """The name of the file."""
        return self._path.name

    @property
    def newlines(self):
        """A string indicating the character sequence used for newlines."""
        return self._file_obj.newlines

    @property
    def modified(self):
        """Whether the file has been modified since the last flush."""
        return self._modified

    @modified.setter
    def modified(self, value):
        """Whether the file has been modified since the last flush."""
        assert value == bool(value)
        assert not self._modified or value
        if value:
            self._modified = True

    def close(self):
        """
        Close and delete the file.

        :return: None
        """
        try:
            if self._file_obj is not None:
                try:
                    self.flush()  # Provides a hook for proxy writebacks.
                finally:
                    self._file_obj.close()
        finally:
            self._file_obj = None
            if hasattr(self, '_path'):
                # If we get an error early enough, __del__ gets called,
                # which calls this function. Hence we have to check if
                # the attribute exists first.
                self._path.discard()

    def flush(self):
        """Flush pending writes to disk."""
        self._file_obj.flush()
        self._modified = False

    def fileno(self):
        """The file number."""
        return self._file_obj.fileno()

    def isatty(self):
        """Is the file a TTY file."""
        return self._file_obj.isatty()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._file_obj)

    def read(self, size=None):
        """
        Read up to size bytes. If no size is specified, read the entire file.

        :param size: The number of bytes to read.
        :return: The bytes read.
        """
        return self._file_obj.read(size)

    def readline(self, limit=-1):
        """
        Read a line from the file. If limit is set, and the line length exceeds the limit, return at
         most limit bytes.

        :param limit: The maximum number of bytes to return.
        :return: The bytes read.
        """
        return self._file_obj.readline(limit)

    def readlines(self, hint=-1):
        """
        Call readline() repeatedly until EOF, returning the results in a list.

        :param hint: A *suggested* maximum number of bytes to read. (May not be respected by
            underlying system call.)
        :return: The bytes read.
        """
        return self._file_obj.readlines(hint)

    def seek(self, offset, whence=io.SEEK_SET):
        """
        Seek to a particular offset in the file.

        :param offset: The offset to seek to.
        :param whence: Indicates the seek origin.
        :return: None
        """
        self._file_obj.seek(offset, whence)

    def tell(self):
        """
        Determine the current position in the file.

        :return: The offset in the file.
        """
        return self._file_obj.tell()

    def truncate(self, size=0):
        """
        Truncate the file. If size is provided, the file is truncated to that size. Otherwise the
        file is made empty.

        :param size: The maximum size of the file.
        :return: None
        """
        self._modified = True
        self._file_obj.truncate(size)

    def write(self, s):
        """
        Write to the file.

        :param s: The string or bytes to write.
        :return: None
        """
        self._modified = True
        self._file_obj.write(s)

    def writelines(self, lines):
        """
        Write a sequence of lines to the file.

        :param lines: The lines to write.
        :return: None
        """
        self._modified = True
        self._file_obj.writelines(lines)
