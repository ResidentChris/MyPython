import unittest

from my_xc import MyXc
from testing_support import FakeProcess, FakeShell, with_shell

ARGUMENTS = {'xc': {'folder': '/app', 'workspace': 'App.xcworkspace', 'scheme': 'App'}}


class MyXcFailureTests(unittest.TestCase):
    def test_test_failure_stops_and_exits_nonzero(self):
        shell = FakeShell([FakeProcess(returncode=65)])
        xc = with_shell(MyXc([], ARGUMENTS, '/repo', '/logs'), shell)
        with self.assertRaises(SystemExit) as raised:
            xc.run(['test', 'test'])
        self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual(len(shell.calls), 1)

    def test_test_success_runs_the_next_command(self):
        shell = FakeShell()
        xc = with_shell(MyXc([], ARGUMENTS, '/repo', '/logs'), shell)
        xc.run(['test', 'test'])
        self.assertEqual(len(shell.calls), 2)


if __name__ == '__main__':
    unittest.main()
