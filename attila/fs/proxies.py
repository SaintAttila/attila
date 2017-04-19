"""
Temporary proxy files
"""


from ..abc.files import Path
from .local import local_fs_connection
from .temp import TempFile


__author__ = 'Aaron Hosford'
__all__ = [
    'ProxyFile'
]


class ProxyFile(TempFile):
    """
    A ProxyFile is a TempFile that acts as a proxy to another file.
    """

    def __init__(self, path, *args, proxy_path=None, writeback=None, **kwargs):
        assert isinstance(path, Path)
        assert writeback is None or callable(writeback)
        if proxy_path is None:
            proxy_path = local_fs_connection.get_temp_file_path(path.name)
            if proxy_path is None:
                raise NotImplementedError()
        elif isinstance(proxy_path, str):
            proxy_path = Path(proxy_path, local_fs_connection())
        else:
            assert isinstance(proxy_path, Path)

        # TODO: Verify that removing this line didn't break anything. It was causing infinite recursion.
        # path.copy_to(proxy_path)

        super().__init__(proxy_path, *args, **kwargs)
        self._original_path = path
        self._writeback = writeback

    @property
    def path(self):
        """The path to the original file object being proxied."""
        return self._original_path

    @property
    def proxy_path(self):
        """The path to the temporary local file acting as a proxy."""
        return self._path

    def flush(self):
        """
        Flush pending writes to disk. If writeback is set, copy changes from the proxy to the
        original file.
        """
        self._file_obj.flush()
        if self._writeback is not None and self._modified:
            self._writeback(self._path, self._original_path)
        self._modified = False
