import unittest

from attila.fs import Path
from attila.fs.ftp import FTPConnector
from attila.security.credentials import Credential


class TestAnonymousFTP(unittest.TestCase):

    user = 'anonymous'
    pw = ''
    server = 'speedtest.tele2.net'
    root = '/'
    folder_path = '/upload'
    file_path = '/512KB.zip'
    bad_path = '/imaginary'

    def setUp(self):
        credential = Credential(self.user, self.pw, self.server)
        self.connector = FTPConnector(self.server, credential, initial_cwd=self.root)
        self.connection = self.connector.connect()
        self.connection.open()

    def testDirChecks(self):
        path = Path(self.folder_path, self.connection)
        self.assert_(path.is_dir)
        self.assertFalse(path.is_file)
        self.assert_(path.exists)

    def testFileChecks(self):
        path = Path(self.file_path, self.connection)
        self.assertFalse(path.is_dir)
        self.assert_(path.is_file)
        self.assert_(path.exists)

    def testNonExistenceChecks(self):
        path = Path(self.bad_path, self.connection)
        self.assertFalse(path.is_dir)
        self.assertFalse(path.is_file)
        self.assertFalse(path.exists)

    def testWalk(self):
        path = Path(self.root, self.connection)
        for parent, subdirs, files in path.walk(onerror=print):
            self.assert_(parent.is_dir)
            self.assertFalse(parent.is_file)
            self.assert_(parent.exists)
            for subdir in subdirs:
                self.assert_(parent[subdir].is_dir)
                self.assertFalse(parent[subdir].is_file)
                self.assert_(parent[subdir].exists)
            for file in files:
                self.assertFalse(parent[file].is_dir)
                self.assert_(parent[file].is_file)
                self.assert_(parent[file].exists)

    def tearDown(self):
        self.connection.close()
