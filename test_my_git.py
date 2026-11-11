import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from my_git import MyGit, my_status, get_all_changes, get_unstaged_changes, popen
from testing_support import FakeProcess, FakeShell, queued_prompt, queued_select


GIT_ENV = {
    **os.environ,
    'GIT_AUTHOR_NAME': 'Test',
    'GIT_AUTHOR_EMAIL': 't@example.com',
    'GIT_COMMITTER_NAME': 'Test',
    'GIT_COMMITTER_EMAIL': 't@example.com',
}


def run_git(*args, cwd):
    subprocess.run(['git', *args], cwd=cwd, check=True,
                    capture_output=True, env=GIT_ENV)


class MyGitDispatchTests(unittest.TestCase):
    def make_git(self):
        return MyGit([], {}, '/fake/repo', '/fake/logs',
                     shell=FakeShell(), prompt=queued_prompt())

    def test_run_dispatches_known_commands(self):
        for command, method in [
            ('pull', 'pull'), ('push', 'push'), ('review', 'diff'),
            ('status', 'status'), ('checkout', 'checkout'),
            ('commit', 'commit'), ('help', 'help'),
        ]:
            git_cmd = self.make_git()
            setattr(git_cmd, method, MagicMock())
            remaining = ['some', 'args']
            git_cmd.run([command] + remaining)
            getattr(git_cmd, method).assert_called_once_with(remaining)

    def test_run_reinserts_unknown_command(self):
        git_cmd = self.make_git()
        commands = ['bogus', 'trailing']
        git_cmd.run(commands)
        self.assertEqual(commands, ['bogus', 'trailing'])

    def test_checkout_without_ticket_argument_does_not_dispatch(self):
        git_cmd = self.make_git()
        git_cmd.checkout = MagicMock()
        git_cmd.run(['checkout'])
        git_cmd.checkout.assert_not_called()


class MyGitPushTests(unittest.TestCase):
    def test_push_force_with_lease_from_repositories_dir(self):
        shell = FakeShell()
        git_cmd = MyGit([], {}, '/fake/repo', '/fake/logs', shell=shell,
                        prompt=queued_prompt())
        git_cmd.push([])
        self.assertEqual(shell.calls, [
            ((["git", "push", "--force-with-lease"],), {'cwd': '/fake/repo'})
        ])


class MyGitPullTests(unittest.TestCase):
    def test_pull_delegates_to_gitpython_origin(self):
        with patch('my_git.git.Repo') as fake_repo_cls:
            fake_repo = fake_repo_cls.return_value
            git_cmd = MyGit([], {}, '/fake/repo', '/fake/logs',
                            shell=FakeShell(), prompt=queued_prompt())
            git_cmd.pull([])
            fake_repo_cls.assert_called_once_with('/fake/repo')
            fake_repo.remotes.origin.pull.assert_called_once()


class MyGitCommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, 'Tickets', '.git'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_commit_writes_ticket_id_and_commits_single_edit(self):
        shell = FakeShell([
            FakeProcess(stdout=b'M  ABC-123_some-ticket.md\n'),
            FakeProcess(),
        ])
        git_cmd = MyGit([], {}, self.tmp, '/fake/logs', shell=shell,
                        prompt=queued_prompt())
        git_cmd.commit([])

        commit_msg_path = os.path.join(self.tmp, 'Tickets', '.git', 'COMMIT_EDITMSG')
        with open(commit_msg_path) as f:
            contents = f.read()
        self.assertTrue(contents.startswith('ABC-123 \n'))
        self.assertEqual(shell.calls[-1], ((['git', 'commit'],), {}))

    def test_commit_does_nothing_for_multiple_edits(self):
        shell = FakeShell([FakeProcess(stdout=b'M  a.md\nM  b.md\n')])
        git_cmd = MyGit([], {}, self.tmp, '/fake/logs', shell=shell,
                        prompt=queued_prompt())
        git_cmd.commit([])

        commit_msg_path = os.path.join(self.tmp, 'Tickets', '.git', 'COMMIT_EDITMSG')
        self.assertFalse(os.path.exists(commit_msg_path))
        self.assertEqual(len(shell.calls), 1)  # only the status check, no commit


class MyGitDiffTests(unittest.TestCase):
    # bar.py then foo.py, both modified and unstaged.
    STATUS = FakeProcess(stdout=b' M bar.py\n M foo.py\n')
    DIFF_FILES = FakeProcess(stdout=(
        b':100644 100644 aaa bbb M\tbar.py\n'
        b':100644 100644 aaa bbb M\tfoo.py\n'
    ))
    NOOP = FakeProcess()

    def test_interactive_review_uses_select_to_choose_a_file(self):
        # diff()'s no-argument path: my_status() (status+diff-files), then
        # get_unstaged_changes() to build the select() menu (status+diff-files),
        # then "clear", then get_unstaged_changes() again post-clear
        # (status+diff-files), then "git diff", then - since the prompt
        # response isn't "D" - a trailing self.status(commands) (status+diff-files).
        shell = FakeShell([
            self.STATUS, self.DIFF_FILES,
            self.STATUS, self.DIFF_FILES,
            self.NOOP,
            self.STATUS, self.DIFF_FILES,
            self.NOOP,
            self.STATUS, self.DIFF_FILES,
        ])
        git_cmd = MyGit([], {}, '/fake/repo', '/fake/logs', shell=shell,
                        prompt=queued_prompt('C'), select=queued_select(1))
        git_cmd.diff([])

        git_diff_calls = [call for call in shell.calls if call[0][0][:2] == ['git', 'diff']]
        self.assertEqual(git_diff_calls[0][0][0], ['git', 'diff', '--', 'foo.py'])

    def test_interactive_review_returns_without_diffing_when_selection_is_cancelled(self):
        # my_status(), then get_unstaged_changes() to build the select()
        # menu - diff() returns (rather than exiting the process) as soon
        # as select() reports a cancellation - e.g. the user pressed escape -
        # before doing anything else. Returning normally, instead of the
        # exit() this replaced, means any commands chained after "review"
        # still get to run rather than the whole process dying here.
        shell = FakeShell([
            self.STATUS, self.DIFF_FILES,
            self.STATUS, self.DIFF_FILES,
        ])
        git_cmd = MyGit([], {}, '/fake/repo', '/fake/logs', shell=shell,
                        prompt=queued_prompt(), select=queued_select(None))

        git_cmd.diff([])

        self.assertFalse(any(call[0][0][:2] == ['git', 'diff'] for call in shell.calls))

    def test_explicit_index_argument_does_not_use_select(self):
        # No my_status()/menu-fetch when an index is passed directly: first
        # call is "clear", then get_unstaged_changes(), then "git diff",
        # then the trailing self.status(commands) after "Cancelled.".
        shell = FakeShell([
            self.NOOP,
            self.STATUS, self.DIFF_FILES,
            self.NOOP,
            self.STATUS, self.DIFF_FILES,
        ])

        def select(items):
            raise AssertionError('select() should not be called with an explicit index argument')

        git_cmd = MyGit([], {}, '/fake/repo', '/fake/logs', shell=shell,
                        prompt=queued_prompt('C'), select=select)
        git_cmd.diff(['2'])

        git_diff_calls = [call for call in shell.calls if call[0][0][:2] == ['git', 'diff']]
        self.assertEqual(git_diff_calls[0][0][0], ['git', 'diff', '--', 'foo.py'])


class MyGitCheckoutInFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        origin = os.path.join(self.tmp, 'origin.git')
        seed = os.path.join(self.tmp, 'seed')
        self.work = os.path.join(self.tmp, 'work')

        run_git('init', '-q', '--bare', origin, cwd=self.tmp)
        run_git('clone', '-q', origin, seed, cwd=self.tmp)
        run_git('checkout', '-q', '-b', 'main', cwd=seed)
        run_git('commit', '-q', '--allow-empty', '-m', 'init', cwd=seed)
        run_git('push', '-q', 'origin', 'main', cwd=seed)

        run_git('checkout', '-q', '-b', 'feature/ABC-123', cwd=seed)
        run_git('commit', '-q', '--allow-empty', '-m', 'work', cwd=seed)
        run_git('push', '-q', 'origin', 'feature/ABC-123', cwd=seed)

        run_git('checkout', '-q', 'main', cwd=seed)
        run_git('checkout', '-q', '-b', 'feature/ABC-123-extra', cwd=seed)
        run_git('commit', '-q', '--allow-empty', '-m', 'more work', cwd=seed)
        run_git('push', '-q', 'origin', 'feature/ABC-123-extra', cwd=seed)

        run_git('clone', '-q', origin, self.work, cwd=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def current_branch(self):
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                cwd=self.work, check=True, capture_output=True)
        return result.stdout.decode('UTF-8').strip()

    def test_checks_out_the_single_matching_branch(self):
        git_cmd = MyGit([], {}, self.work, '/fake/logs', shell=FakeShell(),
                        prompt=queued_prompt())
        status = git_cmd.checkout_in_folder('ABC-123-extra', self.work)
        self.assertEqual(status, 0)
        self.assertEqual(self.current_branch(), 'feature/ABC-123-extra')

    def test_prompts_and_checks_out_the_chosen_branch_on_multiple_matches(self):
        git_cmd = MyGit([], {}, self.work, '/fake/logs', shell=FakeShell(),
                        prompt=queued_prompt('2'))
        git_cmd.checkout_in_folder('ABC-123', self.work)
        self.assertEqual(self.current_branch(), 'feature/ABC-123-extra')

    def test_checks_out_main_directly_regardless_of_match_content(self):
        run_git('checkout', '-q', '-b', 'feature/ABC-123', 'origin/feature/ABC-123', cwd=self.work)
        self.assertEqual(self.current_branch(), 'feature/ABC-123')

        git_cmd = MyGit([], {}, self.work, '/fake/logs', shell=FakeShell(),
                        prompt=queued_prompt())
        git_cmd.checkout_in_folder('main', self.work)
        self.assertEqual(self.current_branch(), 'main')

    def test_checks_out_a_local_only_branch(self):
        run_git('checkout', '-q', '-b', 'feature/XYZ-999', 'origin/main', cwd=self.work)
        run_git('checkout', '-q', 'main', cwd=self.work)

        git_cmd = MyGit([], {}, self.work, '/fake/logs', shell=FakeShell(),
                        prompt=queued_prompt())
        status = git_cmd.checkout_in_folder('XYZ-999', self.work)
        self.assertEqual(status, 0)
        self.assertEqual(self.current_branch(), 'feature/XYZ-999')


class MyGitWorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        origin = os.path.join(self.tmp, 'origin.git')
        seed = os.path.join(self.tmp, 'seed')
        self.work_dir = os.path.join(self.tmp, 'work')

        run_git('init', '-q', '--bare', origin, cwd=self.tmp)
        run_git('clone', '-q', origin, seed, cwd=self.tmp)
        run_git('checkout', '-q', '-b', 'main', cwd=seed)
        run_git('commit', '-q', '--allow-empty', '-m', 'init', cwd=seed)
        run_git('push', '-q', 'origin', 'main', cwd=seed)

        run_git('checkout', '-q', '-b', 'feature/ABC-123', cwd=seed)
        run_git('commit', '-q', '--allow-empty', '-m', 'work', cwd=seed)
        run_git('push', '-q', 'origin', 'feature/ABC-123', cwd=seed)

        run_git('clone', '-q', origin, self.work_dir, cwd=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_work_creates_worktree_under_dot_worktrees(self):
        git_cmd = MyGit([], {}, self.work_dir, '/fake/logs', shell=FakeShell(),
                        prompt=queued_prompt())
        git_cmd.work(['ABC-123'])

        worktree_path = os.path.join(self.work_dir, '.worktrees', 'ABC-123')
        self.assertTrue(os.path.isdir(worktree_path))

        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                cwd=worktree_path, check=True, capture_output=True)
        self.assertEqual(result.stdout.decode('UTF-8').strip(), 'feature/ABC-123')


class MyStatusHelperTests(unittest.TestCase):
    def test_popen_splits_and_drops_blank_lines(self):
        shell = FakeShell([FakeProcess(stdout=b'foo\n\nbar\n')])
        self.assertEqual(popen(['git', 'status'], shell), ['foo', 'bar'])

    def test_popen_strips_each_line_consistently(self):
        # Regression test: popen() used to strip() the whole blob before
        # splitting on newlines, so only the first line's leading space
        # was removed and every later line kept theirs.
        shell = FakeShell([FakeProcess(stdout=b' foo\n bar\n')])
        self.assertEqual(popen(['git', 'status'], shell), ['foo', 'bar'])

    def test_get_all_changes_parses_short_status_output(self):
        shell = FakeShell([FakeProcess(stdout=b' M foo.py\nA  bar.py\n')])
        changes = get_all_changes(shell)
        self.assertEqual([c['path'] for c in changes], ['foo.py', 'bar.py'])

    def test_get_all_changes_pretty_formatting_is_consistent_across_lines(self):
        # Regression test for the "my git review" bug: the first unstaged
        # change was missing its leading space relative to later ones.
        shell = FakeShell([FakeProcess(
            stdout=b' M My/my_git.py\n M My/my_gradle.py\n M My/my_harness.py\n')])
        changes = get_all_changes(shell)
        self.assertEqual(
            [c['pretty'] for c in changes],
            ['M My/my_git.py', 'M My/my_gradle.py', 'M My/my_harness.py'])

    def test_get_unstaged_changes_filters_by_diff_files(self):
        shell = FakeShell([
            FakeProcess(stdout=b' M foo.py\nA  bar.py\n'),
            FakeProcess(stdout=b':100644 100644 aaa bbb M\tfoo.py\n'),
        ])
        unstaged = get_unstaged_changes(shell=shell)
        self.assertEqual([c['path'] for c in unstaged], ['foo.py'])

    def test_my_status_reports_false_when_no_changes(self):
        shell = FakeShell([FakeProcess(stdout=b'')])
        self.assertFalse(my_status(shell))


if __name__ == '__main__':
    unittest.main()
