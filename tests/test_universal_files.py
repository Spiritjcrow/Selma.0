"""Offline regression tests for Selma Universal Files v0.1."""
import tempfile
import unittest
from pathlib import Path

from core.universal_files import FileBoundaryError, LocalFileProvider
from tools.selma_files_server import parse_operation_payload


class LocalProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'a').mkdir()
        (self.root / 'b').mkdir()
        (self.root / 'a' / 'hello.txt').write_text('Selma\n', encoding='utf-8')
        self.fs = LocalFileProvider(self.root)

    def test_list_and_navigate(self):
        self.assertEqual('', self.fs.list_dir()['path'])
        self.assertEqual(['a', 'b'], [x['name'] for x in self.fs.list_dir()['entries']])
        self.assertEqual('a/hello.txt', self.fs.list_dir('a')['entries'][0]['path'])

    def test_copy_move_and_no_overwrite(self):
        self.fs.copy_file('a/hello.txt', 'b')
        self.assertEqual('Selma\n', (self.root / 'b' / 'hello.txt').read_text())
        with self.assertRaises(FileExistsError):
            self.fs.copy_file('a/hello.txt', 'b')
        self.fs.move_file('b/hello.txt', '')
        self.assertFalse((self.root / 'b' / 'hello.txt').exists())
        self.assertTrue((self.root / 'hello.txt').exists())
        with self.assertRaises(FileExistsError):
            self.fs.move_file('a/hello.txt', '')
        self.assertTrue((self.root / 'a' / 'hello.txt').exists())

    def test_create_folder_and_refuse_bad_names(self):
        self.assertEqual({'path': 'a/new'}, self.fs.mkdir('a', 'new'))
        for name in ('..', '.', '../bad', 'a/b', '', '\\absolute'):
            with self.subTest(name=name), self.assertRaises(FileBoundaryError):
                self.fs.mkdir('', name)

    def test_blocks_traversal_and_absolute_paths(self):
        for path in ('../etc', '/etc', 'a/../b', 'a/./hello.txt', 'a\\hello.txt'):
            with self.subTest(path=path), self.assertRaises(FileBoundaryError):
                self.fs.list_dir(path)

    def test_blocks_symlink_traversal(self):
        outside = Path(self.temp.name).parent / 'external-do-not-read'
        (self.root / 'link').symlink_to(outside)
        self.assertEqual('link', self.fs.list_dir()['entries'][-1]['type'])
        with self.assertRaises(FileBoundaryError):
            self.fs.list_dir('link')
        (self.root / 'a' / 'shortcut').symlink_to(self.root / 'a' / 'hello.txt')
        with self.assertRaises(FileBoundaryError):
            self.fs.copy_file('a/shortcut', 'b')

    def test_operation_json_requires_object(self):
        for payload in (b'[]', b'null', b'true', b'17', b'"text"'):
            with self.subTest(payload=payload), self.assertRaises(FileBoundaryError):
                parse_operation_payload(payload)
        self.assertEqual('mkdir', parse_operation_payload(b'{"action":"mkdir"}')['action'])

    def test_copy_does_not_mutate_source(self):
        self.fs.copy_file('a/hello.txt', 'b')
        self.assertEqual((self.root / 'a' / 'hello.txt').read_bytes(), (self.root / 'b' / 'hello.txt').read_bytes())


if __name__ == '__main__':
    unittest.main()
