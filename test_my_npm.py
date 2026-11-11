import os
import shutil
import tempfile
import unittest

from my_npm import MyNpm
from testing_support import FakeShell, queued_prompt


def make_arguments(frontend):
    return {
        'git': {'repos': {'FrontEnd': frontend}},
        'npm': {'wsl_user': 'tester',
                'environment': {'API_A': 'http://localhost:1', 'API_B': 'http://localhost:2'}},
    }


class MyNpmCleanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.node_modules = os.path.join(self.tmp, 'node_modules')
        os.makedirs(os.path.join(self.node_modules, 'some-package'))
        with open(os.path.join(self.node_modules, 'some-package', 'index.js'), 'w') as f:
            f.write('// placeholder')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_deletes_node_modules_and_reinstalls(self):
        shell = FakeShell()
        npm = MyNpm([], make_arguments(self.tmp), '/repo', '/logs',
                   shell=shell, prompt=queued_prompt())
        npm.clean([])
        self.assertFalse(os.path.exists(self.node_modules))
        self.assertEqual(shell.calls, [
            ((['wsl', '--user', 'tester', '--cd', self.tmp, 'npm', 'install'],), {})
        ])


class MyNpmStartTests(unittest.TestCase):
    def test_start_runs_via_wsl_with_environment(self):
        shell = FakeShell()
        npm = MyNpm([], make_arguments('/frontend'), '/repo', '/logs',
                   shell=shell, prompt=queued_prompt())
        npm.start([])
        args, kwargs = shell.calls[0]
        self.assertEqual(kwargs, {})
        command = args[0]
        self.assertEqual(command[:5], ['wsl', '--user', 'tester', '--cd', '/frontend'])
        self.assertEqual(command[5:9], ['export', 'API_A=http://localhost:1;',
                                        'export', 'API_B=http://localhost:2;'])
        self.assertIn('run', command)
        self.assertIn('start', command)


if __name__ == '__main__':
    unittest.main()
