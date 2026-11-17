import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from my_gradle import MyGradle
from testing_support import FakeProcess, FakeShell, queued_prompt


WEBAPPS = [
    {'abbreviation': 'AA', 'name': 'App Alpha', 'module': 'App-Alpha',
     'project': 'app_alpha_webapp', 'war': 'app_alpha.war'},
    {'abbreviation': 'AB', 'name': 'App Beta', 'module': 'App-Beta',
     'project': 'app_beta_webapp', 'war': 'app_beta.war'},
]


def make_arguments(backend, tomcat_home):
    return {
        'git': {'repos': {'Backend': backend}},
        'tomcat': {'tomcat_home': tomcat_home},
        'gradle': {'webapps': WEBAPPS},
    }


class GradlewPresentTestCase(unittest.TestCase):
    """Pretends a gradlew script exists in every directory."""

    def setUp(self):
        patcher = patch('my_gradle.os.path.isfile', return_value=True)
        self.isfile = patcher.start()
        self.addCleanup(patcher.stop)


class MyGradleGradlewTests(unittest.TestCase):
    def test_missing_gradlew_exits_nonzero_without_running_gradle(self):
        shell = FakeShell()
        with tempfile.TemporaryDirectory() as empty:
            with patch('my_gradle.os.getcwd', return_value=empty):
                gradle = MyGradle([], make_arguments('/backend', '/tomcat'),
                                  '/repo', '/logs', shell=shell, prompt=queued_prompt())
                with self.assertRaises(SystemExit) as raised:
                    gradle.clean([])
        self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual(shell.calls, [])

    def test_existing_gradlew_is_used(self):
        shell = FakeShell()
        with tempfile.TemporaryDirectory() as project:
            open(os.path.join(project, 'gradlew'), 'w').close()
            with patch('my_gradle.os.getcwd', return_value=project):
                gradle = MyGradle([], make_arguments('/backend', '/tomcat'),
                                  '/repo', '/logs', shell=shell, prompt=queued_prompt())
                gradle.clean([])
        self.assertEqual(shell.calls, [((['./gradlew', 'clean'],), {'cwd': project})])


class MyGradleCleanFormatTests(GradlewPresentTestCase):
    def test_clean_runs_in_cwd(self):
        shell = FakeShell()
        with patch('my_gradle.os.getcwd', return_value='/cwd/project'):
            gradle = MyGradle([], make_arguments('/backend', '/tomcat'),
                              '/repo', '/logs', shell=shell, prompt=queued_prompt())
            gradle.clean([])
        self.assertEqual(shell.calls, [((["./gradlew", "clean"],), {'cwd': '/cwd/project'})])

    def test_format_runs_in_cwd(self):
        shell = FakeShell()
        with patch('my_gradle.os.getcwd', return_value='/cwd/project'):
            gradle = MyGradle([], make_arguments('/backend', '/tomcat'), '/repo',
                              '/logs', shell=shell, prompt=queued_prompt())
            gradle.format([])
        self.assertEqual(shell.calls, [((['./gradlew', 'format'],), {'cwd': '/cwd/project'})])


class MyGradleInstallTests(GradlewPresentTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_gradle(self, shell, commands=None, prompt=None):
        return MyGradle(commands or [], make_arguments('/backend', '/tomcat'),
                        '/repo', self.tmp, shell=shell,
                        prompt=prompt or queued_prompt())

    def test_install_success_builds_in_cwd(self):
        shell = FakeShell([FakeProcess(returncode=0)])
        with patch('my_gradle.os.getcwd', return_value='/cwd/App-Alpha'):
            gradle = self.make_gradle(shell)
            gradle.install([])
        self.assertEqual(shell.calls, [((['./gradlew', 'build'],), {'cwd': '/cwd/App-Alpha'})])

    def test_install_quickly_assembles_instead_of_building(self):
        shell = FakeShell([FakeProcess(returncode=0)])
        with patch('my_gradle.os.getcwd', return_value='/cwd/App-Alpha'):
            gradle = self.make_gradle(shell)
            gradle.install(['quickly'])
        self.assertEqual(shell.calls, [((['./gradlew', 'assemble'],), {'cwd': '/cwd/App-Alpha'})])

    def test_install_failure_then_continue_runs_remaining_commands(self):
        shell = FakeShell([FakeProcess(returncode=1), FakeProcess(returncode=0)])
        with patch('my_gradle.os.getcwd', return_value='/cwd/App-Alpha'):
            gradle = self.make_gradle(shell, prompt=queued_prompt('y'))
            gradle.install(['clean'])
        self.assertEqual(shell.calls, [
            ((['./gradlew', 'build'],), {'cwd': '/cwd/App-Alpha'}),
            ((['./gradlew', 'clean'],), {'cwd': '/cwd/App-Alpha'}),
        ])

    def test_install_failure_then_abort_exits(self):
        shell = FakeShell([FakeProcess(returncode=1)])
        gradle = self.make_gradle(shell, prompt=queued_prompt('n'))
        with self.assertRaises(SystemExit):
            gradle.install(['clean'])
        self.assertEqual(len(shell.calls), 1)


class MyGradleDeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = os.path.join(self.tmp, 'backend')
        self.tomcat_home = os.path.join(self.tmp, 'tomcat')
        os.makedirs(os.path.join(self.backend, 'App-Alpha',
                                 'app_alpha_webapp', 'build', 'libs'))
        os.makedirs(os.path.join(self.backend, 'App-Beta',
                                 'app_beta_webapp', 'build', 'libs'))
        os.makedirs(os.path.join(self.tomcat_home, 'Webapps'))
        self._write(os.path.join(self.backend, 'App-Alpha',
                                 'app_alpha_webapp', 'build', 'libs',
                                 'app_alpha.war'), 'AA')
        self._write(os.path.join(self.backend, 'App-Beta',
                                 'app_beta_webapp', 'build', 'libs',
                                 'app_beta.war'), 'AB')

    def _write(self, path, contents):
        with open(path, 'w') as f:
            f.write(contents)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_gradle(self, commands=None):
        return MyGradle(commands or [], make_arguments(self.backend, self.tomcat_home),
                        '/repo', '/logs', shell=FakeShell(), prompt=queued_prompt())

    def test_deploy_only_webapp_matching_cwd(self):
        with patch('my_gradle.os.getcwd', return_value='/some/path/App-Alpha'):
            gradle = self.make_gradle()
            gradle.deploy([])
        webapps = os.path.join(self.tomcat_home, 'Webapps')
        self.assertTrue(os.path.exists(os.path.join(webapps, 'app_alpha.war')))
        self.assertFalse(os.path.exists(os.path.join(webapps, 'app_beta.war')))


if __name__ == '__main__':
    unittest.main()
