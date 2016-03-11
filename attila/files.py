import csv
import ctypes
import glob
import logging
import os
import shutil
import stat
import tempfile
import time


log = logging.getLogger(__name__)


# http://msdn.microsoft.com/en-us/library/ie/ms775145(v=vs.85).aspx
INET_E_DOWNLOAD_FAILURE = 0x800C0008

FORM_FEED_CHAR = '\x0C'


class DirectoryNotEmptyError(OSError):
    """
    The operation requires the directory to be empty, and it is not.
    """


# TODO: Use this to make path operations that affect multiple files/folders into atomic operations. The idea is to
#       record everything that has done and, using temp files, make all operations reversible. If an error occurs
#       partway through the transaction, the temp files are then used to roll back the operations performed so far.
#       Otherwise, when all operations have been completed, the temp files are destroyed. Once this class is finished,
#       we can add an "atomic" flag as a parameter to each of the multi-operation methods of Path, which enables the
#       use of transactions.
# class PathTransaction:
#
#     def __init__(self):
#         self._operations = []
#
#     def commit(self):
#         for operation in self._operations:


class Path:

    @classmethod
    def get_temp_dir(cls):
        return cls(tempfile.gettempdir())

    def __init__(self, path_string=''):
        if isinstance(path_string, Path):
            path_string = path_string._path_string
        assert isinstance(path_string, str)
        self._path_string = path_string

    def __str__(self):
        return self._path_string

    def __repr__(self):
        return type(self).__name__ + '(' + repr(self._path_string) + ')'

    def __abs__(self):
        return type(self)(os.path.abspath(self._path_string))

    def __hash__(self):
        return hash(self._path_string)

    def __eq__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        return self._path_string == str(other)

    def __ne__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        return self._path_string != str(other)

    def __lt__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        other = Path(other)

        if len(self._path_string) >= len(other._path_string):
            return False

        current = other.dir
        while current is not None:
            if len(self._path_string) > len(current._path_string):
                return False
            if self._path_string == current._path_string:
                return True
            current = current.dir

        return False

    def __le__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        other = Path(other)

        current = other
        while current is not None:
            if len(self._path_string) > len(current._path_string):
                return False
            if self._path_string == current._path_string:
                return True
            current = current.dir

        return False

    def __gt__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        other = Path(other)

        if len(self._path_string) <= len(other._path_string):
            return False

        current = self.dir
        while current is not None:
            if len(current._path_string) < len(other._path_string):
                return False
            if current._path_string == other._path_string:
                return True
            current = current.dir

        return False

    def __ge__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        other = Path(other)

        current = self
        while current is not None:
            if len(current._path_string) < len(other._path_string):
                return False
            if current._path_string == other._path_string:
                return True
            current = current.dir

        return False

    def __iter__(self):
        if self.is_dir:
            return self.glob()
        else:
            return []

    def __contains__(self, item):
        if isinstance(item, str):
            assert item
            return item in self.list() or Path(item) in self.glob()
        else:
            assert isinstance(item, Path)
            return item in self.glob()

    def __len__(self):
        if not self.is_dir:
            return 0
        return len(os.listdir(self._path_string))

    def __getitem__(self, item):
        assert isinstance(item, (str, Path))
        return Path(os.path.join(self._path_string, str(item)))

    def __and__(self, other):
        if not isinstance(other, (str, Path)):
            return NotImplemented
        this = self
        other = Path(other)
        while this._path_string != other._path_string:
            if len(this._path_string) > len(other._path_string):
                this = this.dir
            elif len(this._path_string) < len(other._path_string):
                other = other.dir
            else:
                this = this.dir
                other = other.dir
            if this is None or other is None:
                return None
        return this

    @property
    def is_dir(self):
        """Whether this path refers to an existing directory."""
        return os.path.isdir(self._path_string)

    @property
    def is_file(self):
        """Whether this path refers to an existing file."""
        return os.path.isfile(self._path_string)

    @property
    def exists(self):
        """Whether this path refers to an existing file system object."""
        return os.path.exists(self._path_string)

    @property
    def protection_mode(self):
        """The protection mode bits of the file system object."""
        return os.stat(self._path_string).st_mode

    @property
    def inode_number(self):
        """The inode number of the file system object."""
        return os.stat(self._path_string).st_ino

    @property
    def device(self):
        """The device of the file system object."""
        return os.stat(self._path_string).st_dev

    @property
    def hard_link_count(self):
        """The number of hard links to the file system object."""
        return os.stat(self._path_string).st_nlink

    @property
    def owner_user_id(self):
        """The user ID of the owner of the file system object."""
        return os.stat(self._path_string).st_uid

    @property
    def owner_group_id(self):
        """The group ID of the owner of the file system object."""
        return os.stat(self._path_string).st_gid

    @property
    def size(self):
        """The size of the file system object."""
        return os.stat(self._path_string).st_size

    @property
    def accessed_time(self):
        """The last time the file system object was accessed."""
        return os.stat(self._path_string).st_atime

    @property
    def modified_time(self):
        """The last time the data of file system object was modified."""
        return os.stat(self._path_string).st_mtime

    @property
    def metadata_changed_time(self):
        """The last time the data or metadata of the file system object was modified."""
        return os.stat(self._path_string).st_ctime

    @property
    def name(self):
        """The name of the file system object."""
        return os.path.basename(self._path_string)

    @property
    def dir(self):
        """The parent directory of the file system object."""
        dir_path = os.path.dirname(self._path_string)
        if dir_path == self._path_string:
            return None
        else:
            return type(self)(dir_path)

    @property
    def bare_name(self):
        """The name of the file system object, minus any extension."""
        return os.path.splitext(os.path.basename(self._path_string))[0]

    @property
    def extension(self):
        """The extension of the file system object, or the empty string."""
        return os.path.splitext(self._path_string)[-1]

    def find(self, include_cwd=True):
        """
        Try to look up the file system object using the PATH system environment variable. Return the located file system
        object (as a Path instance) on success or None on failure. (To modify the PATH, go to Start -> Settings ->
        Control Panel -> System -> Advanced -> Environment Variables, then select PATH in the "System variables" list,
        and click Edit.)

        :param include_cwd: Whether the current working directory be checked before the PATH.
        :return: A Path representing the located object, or None.
        """

        if include_cwd and self.exists:
            return self

        if 'PATH' in os.environ:
            for base in os.environ['PATH'].split(';'):
                path = Path(base)[self]
                if path.exists:
                    return path

        return None

    def list(self, pattern='*'):
        """
        Return a list of the names of the files and directories appearing in this folder.

        :param pattern: A glob-style pattern against which names must match.
        :return: A list of matching file and directory names.
        """
        assert self.is_dir
        return [Path(match).name for match in glob.iglob(os.path.join(self._path_string, pattern))]

    def glob(self, pattern='*'):
        """
        Return a list of the paths to the files and directories appearing in this folder.

        :param pattern: A glob-style pattern against which names must match.
        :return: A list of Path instances for each matching file and directory name.
        """
        assert self.is_dir
        return [Path(match) for match in glob.iglob(os.path.join(self._path_string, pattern))]

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        # TODO: docstring?
        assert self.is_file
        return open(self._path_string, mode, buffering, encoding, errors, newline, closefd, opener)

    def read(self, encoding=None):
        """
        Return an iterator over the lines from the file.

        :param encoding: The file encoding used to open the file.
        :return: An iterator over the lines in the file, without newlines.
        """
        assert self.is_file

        with self.open(mode='r', encoding=encoding) as file_obj:
            for line in file_obj:
                line = line.rstrip('\r\n')
                for piece in line.split(FORM_FEED_CHAR):
                    yield piece

    def load(self, encoding=None):
        """
        Returns a list containing the lines from the file.

        :param encoding: The file encoding used to open the file.
        :return: A list containing the lines in the file, without newlines.
        """
        return list(self.read(encoding))

    def read_delimited(self, delimiter=',', quote='"', encoding=None):
        """
        Return an iterator over the records from the file.

        :param delimiter: The delimiter used to separate fields in each record.
        :param quote: The quote character used to surround field values in the record.
        :param encoding: The file encoding used to open the file.
        :return: An iterator over the rows in the file.
        """
        with self.open(encoding=encoding, newline='') as file_obj:
            reader = csv.reader(file_obj, delimiter=delimiter, quotechar=quote)

            # This is necessary because the reader only keeps a weak reference to the file, which means we can't just
            # return the reader.
            for row in reader:
                yield row

    def load_delimited(self, delimiter=',', quote='"', encoding=None):
        """
        Return a list of the records from the file.

        :param delimiter: The delimiter used to separate fields in each record.
        :param quote: The quote character used to surround field values in the record.
        :param encoding: The file encoding used to open the file.
        :return: A list containing the rows in the file.
        """
        return list(self.read_delimited(delimiter, quote, encoding))

    def save(self, lines, overwrite=False, append=False, encoding=None):
        """
        Save a sequence of lines to a file.

        :param lines: An iterator or iterable container over the lines to be written.
        :param overwrite: Whether to overwrite the file if it already exists.
        :param append: Whether to append to the file if it already exists.
        :param encoding: The encoding of the file.
        :return: The number of lines written.
        """
        assert not overwrite or not append
        assert not self.exists or ((overwrite or append) and self.is_file)

        with self.open(mode=('a' if append else 'w'), encoding=encoding) as file_obj:
            index = -1
            for index, line in enumerate(lines):
                file_obj.write(line.rstrip('\r\n') + '\n')
            return index + 1

    def save_delimited(self, rows, delimiter=',', quote='"', overwrite=False, append=False, encoding=None):
        """
        Save a sequence of rows to a file.

        :param rows: An iterator or iterable container over the rows to be written.
        :param delimiter: The delimiter used to separate fields in a given row.
        :param quote: The quote character used to surround field values.
        :param overwrite: Whether to overwrite the file if it already exists.
        :param append: Whether to append to the file if it already exists.
        :param encoding: The encoding of the file.
        :return: The number of lines written.
        """
        assert not overwrite or not append
        assert not self.exists or ((overwrite or append) and self.is_file)

        with self.open(mode=('a' if append else 'w'), encoding=encoding, newline='') as file_obj:
            writer = csv.writer(file_obj, delimiter=delimiter, quotechar=quote)
            index = -1
            for index, row in enumerate(rows):
                writer.writerow(row)
            return index + 1

    def is_available(self, mode='r'):
        """
        Check to see if the file is available to read or write.

        :param mode: The desired access to the file, either 'r' (default) or 'w'.
        """

        assert mode in ('r', 'w')

        if not self.exists:
            return mode == 'w'

        assert not self.is_dir

        if mode == 'w':
            open_mode = 'a'
        else:
            open_mode = 'r'

        # Try to open the file, then immediately close it again. This will error if the file cannot be accessed, but it
        # won't change the contents of the file in any case.
        # noinspection PyBroadException
        try:
            with open(self._path_string, mode=open_mode):
                return True
        except Exception:
            return False

    def is_stable(self, interval=None):
        """
        Watches for file size changes over time.  Returns a Boolean indicating whether the file's size was constant
        over the given interval.

        :param interval: The number of seconds to wait between checks. Default is 1 second.
        """

        assert interval is None or interval > 0
        if interval is None:
            interval = 1

        initial_size = self.size
        time.sleep(interval)
        return initial_size == self.size

    def remove(self):
        """
        Recursively remove the folder or file.
        """

        assert self.exists

        if not os.access(self._path_string, os.W_OK):
            os.chmod(self._path_string, stat.S_IWRITE)

        if self.is_dir:
            for child in self.glob():
                child.remove()
            os.rmdir(self._path_string)
        else:
            os.remove(self._path_string)

    def discard(self):
        """
        Recursively remove the folder or file.
        """

        if self.exists:
            self.remove()

    def make_dir(self, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Create a directory at this location.

        :param overwrite: Whether existing files/folders that conflict with this function are to be deleted/overwritten.
        :param clear: Whether the directory at this location must be empty for the function to be satisfied.
        :param fill: Whether the necessary parent folder(s) are to be created if the do not exist already.
        :param check_only: Whether the function should only check if it's possible, or actually perform the operation.
        :return: None
        """

        if check_only is None:
            # First check to see if it can be done before we actually make any changes. This doesn't make the whole
            # thing perfectly atomic, but it eliminates most cases where we start to do things and then find out
            # we shouldn't have.
            self.make_dir(overwrite, clear, fill, check_only=True)
            check_only = False  # If we don't do this, we'll do a redundant check first on each step in the recursion.

        if self.is_dir:
            if clear:
                children = self.glob()
                if children:
                    if not overwrite:
                        raise DirectoryNotEmptyError(self)
                    if not check_only:
                        for child in children:
                            child.remove()
        elif self.exists:
            # It's not a folder, and it's in our way.
            if not overwrite:
                raise FileExistsError(self)
            if not check_only:
                self.remove()
                os.mkdir(self._path_string)
        else:
            # The path doesn't exist yet, so we need to create it.

            # First ensure the parent folder exists.
            if not self.dir.is_dir:
                if not fill:
                    raise NotADirectoryError(self.dir)
                self.dir.make_dir(overwrite, clear=False, fill=True, check_only=check_only)

            # Then create the target folder.
            if not check_only:
                os.mkdir(self._path_string)

    def copy_into(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Recursively copy the folder or file to the destination. The file or folder is added to the destination folder's
        listing and is not renamed in the process.

        :param destination: The location of the containing folder where this file system object will be copied.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the destination folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually perform the operation.
        :return: None
        """

        self.copy_to(destination[self.name], overwrite, clear, fill, check_only)

    def copy_to(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Recursively copy the folder or file to the destination. The file or folder is renamed to the destination's name
        in the process if the names differ.

        :param destination: The new location where this file system object will be copied.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the parent folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually perform the operation.
        :return: None
        """

        if check_only is None:
            # First check to see if it can be done before we actually make any changes. This doesn't make the whole
            # thing perfectly atomic, but it eliminates most cases where we start to do things and then find out
            # we shouldn't have.
            self.copy_into(destination, overwrite, clear, fill, check_only=True)
            check_only = False  # If we don't do this, we'll do a redundant check first on each step in the recursion.

        assert isinstance(destination, (str, Path))
        destination = Path(destination)

        assert self.exists

        # Create the target directory, if necessary. Do not clear it, regardless of the clear flag's value, as this is
        # the new *parent* folder of the file object to be copied, and the clear flag only applies to the copied file
        # object and its descendants.
        destination.dir.make_dir(overwrite, clear=False, fill=fill, check_only=check_only)

        if self.is_dir:
            destination.make_dir(overwrite, clear, fill, check_only)
            for child in self.glob():
                child.copy_into(destination, overwrite, clear, fill, check_only)
        else:
            assert self.exists

            if destination.exists:
                # It's not a folder, and it's in our way.
                if not overwrite:
                    if destination.is_dir:
                        raise IsADirectoryError(destination)
                    else:
                        raise FileExistsError(destination)
                if not check_only:
                    destination.remove()
            if not check_only:
                shutil.copy2(self._path_string, destination._path_string)

    def move_into(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Move the folder or file to the destination. The file or folder is added to the destination folder's listing and
        is not renamed in the process.

        :param destination: The location of the containing folder where this file system object will be moved.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the destination folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually perform the operation.
        :return: None
        """

        self.move_to(destination[self.name], overwrite, clear, fill, check_only)

    def move_to(self, destination, overwrite=False, clear=False, fill=True, check_only=None):
        """
        Move the folder or file to the destination. The file or folder is renamed to the destination's name in the
        process if the names differ.

        :param destination: The new location where this file system object will be moved.
        :param overwrite: Whether conflicting files or folders should be overwritten.
        :param clear: Whether pre-existing contents of a folder are considered to be a conflict.
        :param fill: Whether the parent folder is created if it doesn't exist.
        :param check_only: Whether the function should only check if it's possible, or actually perform the operation.
        :return: None
        """

        if check_only is None:
            # First check to see if it can be done before we actually make any changes. This doesn't make the whole
            # thing perfectly atomic, but it eliminates most cases where we start to do things and then find out
            # we shouldn't have.
            self.move_into(destination, overwrite, clear, fill, check_only=True)
            check_only = False  # If we don't do this, we'll do a redundant check first on each step in the recursion.

        assert isinstance(destination, (str, Path))
        destination = Path(destination)

        assert self.exists

        # Create the target directory, if necessary. Do not clear it, regardless of the clear flag's value, as this is
        # the new *parent* folder of the file object to be copied, and the clear flag only applies to the copied file
        # object and its descendants.
        destination.dir.make_dir(overwrite, clear=False, fill=fill, check_only=check_only)

        if self.is_dir:
            destination.make_dir(overwrite, clear, fill, check_only)
            for child in self.glob():
                child.move_into(destination, overwrite, clear, fill, check_only)
        else:
            assert self.exists

            if destination.exists:
                # It's not a folder, and it's in our way.
                if not overwrite:
                    if destination.is_dir:
                        raise IsADirectoryError(destination)
                    else:
                        raise FileExistsError(destination)
                if not check_only:
                    destination.remove()
            if not check_only:
                # os.rename can't move a file to a different drive, so we have to use shutil.move instead.
                shutil.move(self._path_string, destination._path_string)

    def download_from(self, url, overwrite=False, fill=False):
        """
        Try to download the file from the given URL. IMPORTANT: This method hangs in Windows Vista. If you use it in a
        script that runs from a scheduled task, you must make sure that the scheduled task is configured for Windows 7
        and not Windows Vista at the bottom of the General tab.

        :param url: The URL of the file to be downloaded.
        :param overwrite: Whether to overwrite the file if it already exists locally.
        :param fill: Whether to create the parent directory if it doesn't exist.
        :return: None
        """

        if not isinstance(url, str):
            raise TypeError("Expected string value for url, got " + repr(url))

        if not fill and not self.dir.is_dir:
            raise NotADirectoryError(self.dir)

        if not overwrite and self.exists:
            raise FileExistsError(self)

        # URLDownloadToFileW cannot download directly to a network path, so we have to download to a local path first
        # and move it to the network.
        temp_path = self.get_temp_dir()[self.name + '_' + time.strftime('%Y%m%d%H%M%S')]

        try:
            # http://msdn.microsoft.com/en-us/library/ie/ms775123(v=vs.85).aspx
            result = ctypes.windll.urlmon.URLDownloadToFileW(0, url, temp_path, 0, 0)

            if result == 1:
                raise MemoryError(
                    "Insufficient memory available to download " + url + " to " + str(self) + ". (Return code 1)"
                )
            elif result != 0:
                raise RuntimeError(
                    "Unspecified error while trying to download " + url + " to " + str(self) +
                    ". (Return code " + str(result) + ")"
                )
            elif not os.path.isfile(temp_path):
                raise FileNotFoundError(
                    "File appeared to download successfully from " + url + " but could not be found afterward."
                )

            temp_path.move_to(self, overwrite, clear=False, fill=fill)
        finally:
            # noinspection PyBroadException
            try:
                temp_path.discard()
            except Exception:
                pass  # We were just being polite anyway...

    def find_unique_file(self, pattern='*', most_recent=True):
        """
        Find a file in the folder matching the given pattern and return it. If no such file is found, return None. If
        multiple files are found, either disambiguate by recency if most_recent is set, or raise an exception if
        most_recent is not set.

        :param pattern: The pattern which the file must match. Default is '*" (all files).
        :param most_recent: Whether to use recency to disambiguate when multiple files are matched by the pattern.
        :return: The uniquely identified file, as a Path instance, or None.
        """

        if not self.is_dir:
            raise NotADirectoryError(self)

        # Get a list of files matching the pattern. Ignore Microsoft Office temporary files, which start with '~$'.
        files = [path for path in self.glob(pattern) if not path.name.startswith('~$')]

        # If nothing was found, return None
        if not files:
            log.info("No file found matching the pattern %s in the folder %s.", pattern, self)
            return None

        # Log the files we found
        if log.level <= logging.INFO:
            log.info("Source file(s) identified:")
            for file_path in files:
                log.info("    %s", str(file_path))

        # If only one file was found, return it. Otherwise, either blow up or use
        # the most recent, depending on parameter settings.
        if len(files) == 1:
            return files[0]
        elif most_recent:
            log.info("Only the most recent file will be used.")
            result = max(files, key=lambda path: path.modified_time)
            log.info("Most recent file: %s", result)
            return result
        else:
            raise FileExistsError("Multiple files identified matching the pattern %s in folder %s." % (pattern, self))
