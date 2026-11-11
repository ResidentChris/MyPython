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


class MyGradleCleanFormatTests(unittest.TestCase):
    def test_clean_here_runs_in_cwd(self):
        shell = FakeShell()
        with patch('my_gradle.os.getcwd', return_value='/cwd/project'):
            gradle = MyGradle(['here'], make_arguments('/backend', '/tomcat'),
                              '/repo', '/logs', shell=shell, prompt=queued_prompt())
            gradle.clean([])
        self.assertEqual(shell.calls, [((["gradle", "clean"],), {'cwd': '/cwd/project'})])

    def test_clean_not_here_runs_in_backend(self):
        shell = FakeShell()
        gradle = MyGradle([], make_arguments('/backend', '/tomcat'), '/repo',
                          '/logs', shell=shell, prompt=queued_prompt())
        gradle.clean([])
        self.assertEqual(shell.calls, [((["gradle", "clean"],), {'cwd': '/backend'})])

    def test_format_runs_in_backend(self):
        shell = FakeShell()
        gradle = MyGradle([], make_arguments('/backend', '/tomcat'), '/repo',
                          '/logs', shell=shell, prompt=queued_prompt())
        gradle.format([])
        self.assertEqual(shell.calls, [((['gradle', 'format'],), {'cwd': '/backend'})])


class MyGradleInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_gradle(self, shell, commands=None, prompt=None):
        return MyGradle(commands or [], make_arguments('/backend', '/tomcat'),
                        '/repo', self.tmp, shell=shell,
                        prompt=prompt or queued_prompt())

    def test_install_success_builds_backend(self):
        shell = FakeShell([FakeProcess(returncode=0)])
        gradle = self.make_gradle(shell)
        gradle.install([])
        self.assertEqual(shell.calls, [((['gradle', 'build'],), {'cwd': '/backend'})])

    def test_install_quickly_assembles_instead_of_building(self):
        shell = FakeShell([FakeProcess(returncode=0)])
        gradle = self.make_gradle(shell, commands=['quickly'])
        gradle.install(['quickly'])
        self.assertEqual(shell.calls, [((['gradle', 'assemble'],), {'cwd': '/backend'})])

    def test_install_here_builds_in_cwd(self):
        shell = FakeShell([FakeProcess(returncode=0)])
        with patch('my_gradle.os.getcwd', return_value='/cwd/App-Alpha'):
            gradle = self.make_gradle(shell, commands=['here'])
            gradle.install([])
        self.assertEqual(shell.calls, [((['gradle', 'build'],), {'cwd': '/cwd/App-Alpha'})])

    def test_install_failure_then_continue_does_not_retry_gradle(self):
        shell = FakeShell([FakeProcess(returncode=1)])
        gradle = self.make_gradle(shell, prompt=queued_prompt('c'))
        gradle.install(['tomcat'])
        self.assertEqual(len(shell.calls), 1)

    def test_install_failure_then_retry_runs_gradle_again(self):
        shell = FakeShell([FakeProcess(returncode=1), FakeProcess(returncode=0)])
        gradle = self.make_gradle(shell, prompt=queued_prompt('r'))
        gradle.install([])
        self.assertEqual(len(shell.calls), 2)
        self.assertEqual(shell.calls[0], ((['gradle', 'build'],), {'cwd': '/backend'}))
        self.assertEqual(shell.calls[1], ((['gradle', 'build'],), {'cwd': '/backend'}))


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

    def test_deploy_not_here_copies_both_wars(self):
        gradle = self.make_gradle()
        gradle.deploy([])
        webapps = os.path.join(self.tomcat_home, 'Webapps')
        self.assertTrue(os.path.exists(os.path.join(webapps, 'app_alpha.war')))
        self.assertTrue(os.path.exists(os.path.join(webapps, 'app_beta.war')))

    def test_deploy_here_first_webapp_only(self):
        with patch('my_gradle.os.getcwd', return_value='/some/path/App-Alpha'):
            gradle = self.make_gradle(['here'])
            gradle.deploy([])
        webapps = os.path.join(self.tomcat_home, 'Webapps')
        self.assertTrue(os.path.exists(os.path.join(webapps, 'app_alpha.war')))
        self.assertFalse(os.path.exists(os.path.join(webapps, 'app_beta.war')))


if __name__ == '__main__':
    unittest.main()
