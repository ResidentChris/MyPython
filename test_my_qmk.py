import unittest

from my_qmk import MyQmk
from testing_support import FakeProcess, FakeShell, with_shell

ARGUMENTS = {'qmk': {'folder': '/qmk', 'keyboard': 'board', 'keymap': 'map'}}


class MyQmkFailureTests(unittest.TestCase):
    def test_failure_stops_and_exits_nonzero(self):
        for command in ['compile', 'flash']:
            with self.subTest(command=command):
                shell = FakeShell([FakeProcess(returncode=1)])
                qmk = with_shell(MyQmk([], ARGUMENTS, '/repo', '/logs'), shell)
                with self.assertRaises(SystemExit) as raised:
                    qmk.run([command, 'compile'])
                self.assertNotEqual(raised.exception.code, 0)
                self.assertEqual(shell.calls, [
                    ((['qmk', command, '-kb', 'board', '-km', 'map'],), {'cwd': '/qmk'}),
                ])

    def test_success_runs_the_next_command(self):
        shell = FakeShell()
        qmk = with_shell(MyQmk([], ARGUMENTS, '/repo', '/logs'), shell)
        qmk.run(['compile', 'flash'])
        self.assertEqual([call[0][0][1] for call in shell.calls], ['compile', 'flash'])


if __name__ == '__main__':
    unittest.main()
