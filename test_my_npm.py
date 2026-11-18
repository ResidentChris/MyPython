import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from my_npm import MyNpm
from testing_support import FakeShell, queued_prompt, with_shell



class NpmTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cwd = patch('my_npm.os.getcwd', return_value=self.tmp)
        cwd.start()
        self.addCleanup(cwd.stop)
        self.shell = FakeShell()
        self.npm = with_shell(MyNpm([], {}, '/repo', '/logs', prompt=queued_prompt()), self.shell)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class MyNpmCleanTests(NpmTestCase):
    def test_clean_deletes_node_modules_and_reinstalls_in_the_current_directory(self):
        node_modules = os.path.join(self.tmp, 'node_modules')
        os.makedirs(os.path.join(node_modules, 'some-package'))
        with patch('builtins.print'):
            self.npm.clean([])
        self.assertFalse(os.path.exists(node_modules))
        self.assertEqual(self.shell.calls, [((['npm', 'install'],), {'cwd': self.tmp})])

    def test_clean_without_node_modules_still_installs(self):
        with patch('builtins.print'):
            self.npm.clean([])
        self.assertEqual(self.shell.calls, [((['npm', 'install'],), {'cwd': self.tmp})])


class MyNpmStartTests(NpmTestCase):
    def test_start_runs_npm_start_in_the_current_directory(self):
        self.npm.start([])
        self.assertEqual(self.shell.calls, [((['npm', 'run', 'start'],), {'cwd': self.tmp})])


if __name__ == '__main__':
    unittest.main()
