import unittest
from unittest.mock import patch

from my_harness import MyHarness
from testing_support import FakeShell, with_shell

ARGUMENTS = {'harness': {'folder': '/harness', 'url': 'https://localhost:8080'}}


class MyHarnessWebTests(unittest.TestCase):
    def setUp(self):
        self.shell = FakeShell()
        self.harness = with_shell(MyHarness([], ARGUMENTS, '/repo', '/logs'), self.shell)
        for name in ['builtins.print', 'my_harness.wait']:
            patcher = patch(name)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_harness(self, commands):
        self.harness.run(commands)
        return [call[0][0] for call in self.shell.calls]

    def test_build_leaves_the_next_commands_for_my(self):
        commands = ['web', 'build', 'git', 'status']
        run = self.run_harness(commands)
        self.assertEqual(commands, ['git', 'status'])
        self.assertEqual(run, [['npm', 'install']])

    def test_run_leaves_the_next_commands_for_my(self):
        commands = ['web', 'run', 'git', 'status']
        run = self.run_harness(commands)
        self.assertEqual(commands, ['git', 'status'])
        self.assertEqual(run[0], ['npm', 'run', 'harness:web'])

    def test_web_on_its_own_runs_the_harness(self):
        commands = ['web', 'git']
        run = self.run_harness(commands)
        self.assertEqual(commands, ['git'])
        self.assertEqual(run[0], ['npm', 'run', 'harness:web'])

    def test_build_then_run(self):
        commands = ['web', 'build', 'run']
        run = self.run_harness(commands)
        self.assertEqual(commands, [])
        self.assertEqual(run[:2], [['npm', 'install'], ['npm', 'run', 'harness:web']])

    def test_harness_commands_after_web_still_run(self):
        commands = ['web', 'build', 'ios']
        self.run_harness(commands)
        self.assertEqual(commands, [])


if __name__ == '__main__':
    unittest.main()
