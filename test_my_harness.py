import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from my_harness import MyHarness, wait
from testing_support import FakeProcess, FakeShell, with_shell

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

    def test_build_failure_stops_and_exits_nonzero(self):
        self.shell = FakeShell([FakeProcess(returncode=1)])
        with_shell(self.harness, self.shell)
        with self.assertRaises(SystemExit) as raised:
            self.run_harness(['web', 'build', 'run'])
        self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual([call[0][0] for call in self.shell.calls], [['npm', 'install']])

    def test_harness_commands_after_web_still_run(self):
        commands = ['web', 'build', 'ios']
        self.run_harness(commands)
        self.assertEqual(commands, [])



class MyHarnessWebRunTests(unittest.TestCase):
    def test_keeps_reading_the_harness_output_after_it_has_compiled(self):
        # A harness that compiles, then writes more than a pipe's buffer can hold.
        harness_process = subprocess.Popen(
            [sys.executable, '-c',
             "import sys; print('compiled successfully', flush=True); sys.stdout.write('x' * 1000000)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(harness_process.kill)

        harness = MyHarness([], ARGUMENTS, '/repo', '/logs')
        harness.start_web_harness = lambda: harness_process
        harness.start_chromium = lambda: FakeProcess()

        with patch('builtins.print'):
            running = threading.Thread(target=harness.web_run, daemon=True)
            running.start()
            running.join(timeout=10)
        self.assertFalse(running.is_alive(), 'the harness blocked writing its output')
        self.assertEqual(harness_process.returncode, 0)


class WaitTests(unittest.TestCase):
    def test_stops_reading_after_the_line_with_the_given_text(self):
        process = FakeProcess(stdout=b'starting\n\033[32mServer READY\033[0m\nlater\n')
        with patch('builtins.print'):
            wait(process, 'server ready')
        self.assertEqual(process.stdout.read(), 'later\n')


if __name__ == '__main__':
    unittest.main()
