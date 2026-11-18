import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import git

from my_git import MyGit, REFRESH, default_select
from testing_support import FakeProcess, FakeShell, queued_prompt, queued_select, with_shell


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
        return with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                     prompt=queued_prompt()), FakeShell())

    def test_run_dispatches_known_commands(self):
        for command, method in [
            ('pull', 'pull'), ('push', 'push'), ('review', 'diff'),
            ('add', 'add_untracked'), ('stage', 'add_untracked'),
            ('status', 'status'), ('checkout', 'checkout'),
            ('commit', 'commit'), ('help', 'help'), ('branch', 'branch'),
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
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt()), shell)
        git_cmd.push([])
        self.assertEqual(shell.calls, [
            ((["git", "push", "--force-with-lease"],), {'cwd': '/fake/repo'})
        ])

    def test_push_up_sets_upstream_to_the_current_branch_on_origin(self):
        shell = FakeShell()
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt()), shell)
        commands = ['up']
        git_cmd.push(commands)
        self.assertEqual(commands, [])
        self.assertEqual(shell.calls, [
            ((["git", "push", "--force-with-lease", "--set-upstream", "origin", "HEAD"],),
             {'cwd': '/fake/repo'})
        ])

    def test_push_up_continues_with_remaining_commands(self):
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt()), FakeShell())
        git_cmd.run = MagicMock()
        git_cmd.push(['up', 'status'])
        git_cmd.run.assert_called_once_with(['status'])

    def test_push_without_up_leaves_other_commands_alone(self):
        shell = FakeShell()
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt()), shell)
        git_cmd.run = MagicMock()
        git_cmd.push(['status'])
        self.assertEqual(shell.calls[0][0][0], ["git", "push", "--force-with-lease"])
        git_cmd.run.assert_called_once_with(['status'])


class MyGitPullTests(unittest.TestCase):
    def test_pull_delegates_to_gitpython_origin(self):
        with patch('my_git.git.Repo') as fake_repo_cls:
            fake_repo = fake_repo_cls.return_value
            git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                            prompt=queued_prompt()), FakeShell())
            git_cmd.pull([])
            fake_repo_cls.assert_called_once_with('/fake/repo')
            fake_repo.remote.assert_called_once_with('origin')
            fake_repo.remote.return_value.pull.assert_called_once()

    def test_pull_without_an_origin_remote_explains_and_exits(self):
        with patch('my_git.git.Repo') as fake_repo_cls, patch('builtins.print') as printed:
            fake_repo_cls.return_value.remote.side_effect = ValueError("Remote named 'origin' didn't exist")
            git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                            prompt=queued_prompt()), FakeShell())
            with self.assertRaises(SystemExit) as raised:
                git_cmd.pull([])
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("No remote called 'origin'", printed.call_args[0][0])


class MyGitFailureTests(unittest.TestCase):
    def failing_run(self, error):
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                                   prompt=queued_prompt()), FakeShell())
        git_cmd.pull = MagicMock(side_effect=error)
        with patch('builtins.print') as printed, self.assertRaises(SystemExit) as raised:
            git_cmd.run(['pull', 'status'])
        self.assertEqual(raised.exception.code, 1)
        return printed.call_args[0][0]

    def test_failed_git_command_shows_the_command_and_gits_message(self):
        error = git.GitCommandError(['git', 'pull', '-v', '--', 'origin'], 1,
                                    stderr="error: Your local changes would be overwritten by merge:\nhint: commit first")
        message = self.failing_run(error)
        self.assertIn('git pull -v -- origin failed: Your local changes would be overwritten by merge:', message)
        self.assertNotIn('hint', message)
        self.assertNotIn('Traceback', message)

    def test_not_a_repository(self):
        message = self.failing_run(git.InvalidGitRepositoryError('/not/a/repo'))
        self.assertIn('Not a git repository: /not/a/repo', message)

    def test_missing_folder(self):
        message = self.failing_run(git.NoSuchPathError('/missing'))
        self.assertIn('No such folder: /missing', message)


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
        git_cmd = with_shell(MyGit([], {}, self.tmp, '/fake/logs',
                        prompt=queued_prompt()), shell)
        git_cmd.commit([])

        commit_msg_path = os.path.join(self.tmp, 'Tickets', '.git', 'COMMIT_EDITMSG')
        with open(commit_msg_path) as f:
            contents = f.read()
        self.assertTrue(contents.startswith('ABC-123 \n'))
        self.assertEqual(shell.calls[-1], ((['git', 'commit'],), {}))

    def test_commit_does_nothing_for_multiple_edits(self):
        shell = FakeShell([FakeProcess(stdout=b'M  a.md\nM  b.md\n')])
        git_cmd = with_shell(MyGit([], {}, self.tmp, '/fake/logs',
                        prompt=queued_prompt()), shell)
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
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt('C'), select=queued_select(1)), shell)
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
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt(), select=queued_select(None)), shell)

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

        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                        prompt=queued_prompt('C'), select=select), shell)
        git_cmd.diff(['2'])

        git_diff_calls = [call for call in shell.calls if call[0][0][:2] == ['git', 'diff']]
        self.assertEqual(git_diff_calls[0][0][0], ['git', 'diff', '--', 'foo.py'])

    def test_u_reverts(self):
        for key in ['u', 'U']:
            with self.subTest(key=key):
                shell = FakeShell([
                    self.NOOP,
                    self.STATUS, self.DIFF_FILES,
                    self.NOOP,
                    self.NOOP,
                    self.STATUS, self.DIFF_FILES,
                ])
                git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                                prompt=queued_prompt(key)), shell)
                with patch('builtins.print'):
                    git_cmd.diff(['2'])
                calls = [call[0] for call in shell.calls]
                self.assertIn((['git', 'checkout', '--', 'foo.py'],), calls)

    def test_r_and_d_refresh_the_diff_without_reverting(self):
        for key in ['r', 'R', 'd', 'D']:
            with self.subTest(key=key):
                shell = FakeShell([
                    self.NOOP, self.STATUS, self.DIFF_FILES, self.NOOP,
                    self.NOOP, self.STATUS, self.DIFF_FILES, self.NOOP,
                    self.STATUS, self.DIFF_FILES,
                ])
                git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                                prompt=queued_prompt(key, 'c')), shell)
                with patch('builtins.print'):
                    git_cmd.diff(['2'])
                calls = [call[0][0] for call in shell.calls]
                self.assertEqual(calls.count(['git', 'diff', '--', 'foo.py']), 2)
                self.assertNotIn(['git', 'checkout', '--', 'foo.py'], calls)

    def test_a_and_s_both_run_git_add(self):
        for key in ['a', 'A', 's', 'S']:
            with self.subTest(key=key):
                shell = FakeShell([
                    self.NOOP,
                    self.STATUS, self.DIFF_FILES,
                    self.NOOP,
                    self.NOOP,
                    self.STATUS, self.DIFF_FILES,
                ])
                git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                                prompt=queued_prompt(key)), shell)
                with patch('builtins.print'):
                    git_cmd.diff(['2'])
                self.assertIn((['git', 'add', '--', 'foo.py'],), [call[0] for call in shell.calls])


class DefaultSelectTests(unittest.TestCase):
    """Drives the real arrow-key list with simulated keypresses."""

    def press(self, keys):
        from prompt_toolkit.application import create_app_session
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
            pipe.send_text(keys)
            return default_select(['one', 'two'])

    def test_r_and_d_ask_for_a_refresh(self):
        for key in ['r', 'R', 'd', 'D']:
            with self.subTest(key=key):
                self.assertEqual(self.press(key), REFRESH)

    def test_arrows_and_enter_pick_an_item(self):
        self.assertEqual(self.press('\x1b[B\r'), 1)

    def test_escape_cancels(self):
        self.assertIsNone(self.press('\x1b'))


class MyGitChooseTests(unittest.TestCase):
    def make_git(self, *selections):
        return with_shell(MyGit([], {}, '/fake/repo', '/fake/logs', prompt=queued_prompt(),
                                select=queued_select(*selections)), FakeShell())

    def test_refresh_fetches_the_items_again(self):
        lists = iter([['a', 'b'], ['b', 'c', 'd']])
        index, items = self.make_git(REFRESH, 2).choose(lambda: next(lists))
        self.assertEqual((index, items), (2, ['b', 'c', 'd']))

    def test_nothing_to_choose_from_does_not_show_the_list(self):
        def select(items):
            raise AssertionError('select() should not be called')
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs', prompt=queued_prompt(),
                                   select=select), FakeShell())
        self.assertEqual(git_cmd.choose(lambda: []), (None, []))

    def test_refreshing_to_an_empty_list_stops(self):
        lists = iter([['a'], []])
        self.assertEqual(self.make_git(REFRESH).choose(lambda: next(lists)), (None, []))

    def test_branch_matches_are_fetched_again_on_refresh(self):
        branches = iter(['  feature/ABC-1\n  feature/ABC-1-x\n',
                         '  feature/ABC-1\n  feature/ABC-1-x\n  feature/ABC-1-new\n'])
        branch = self.make_git(REFRESH, 2).resolve_branch('ABC-1', lambda: next(branches))
        self.assertEqual(branch, 'feature/ABC-1-new')


class MyGitBranchTests(unittest.TestCase):
    def make_git(self, shell, answers=()):
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                                   prompt=queued_prompt(*answers)), shell)
        git_cmd.run = MagicMock()
        return git_cmd

    def test_creates_the_branch_and_switches_to_it(self):
        git_cmd = self.make_git(FakeShell())
        with patch('my_git.git.Repo') as fake_repo_cls:
            git_cmd.branch(['feature/new', 'status'])
        fake_repo_cls.assert_called_once_with('/fake/repo')
        fake_repo_cls.return_value.git.switch.assert_called_once_with('-c', 'feature/new')
        git_cmd.run.assert_called_once_with(['status'])

    def test_without_a_name_is_not_dispatched(self):
        git_cmd = with_shell(MyGit([], {}, '/fake/repo', '/fake/logs', prompt=queued_prompt()), FakeShell())
        git_cmd.branch = MagicMock()
        git_cmd.run(['branch'])
        git_cmd.branch.assert_not_called()

    def test_list_and_dash_dash_list_list_branches_without_creating_one(self):
        for name in ['list', '--list']:
            with self.subTest(name=name):
                shell = FakeShell()
                git_cmd = self.make_git(shell)
                with patch('builtins.print'):
                    git_cmd.branch([name, 'status'])
                self.assertEqual(shell.calls, [((['git', 'branch', '--list'],), {'cwd': '/fake/repo'})])
                git_cmd.run.assert_called_once_with(['status'])

    def test_failure_reports_git_error_and_stops_further_commands(self):
        git_cmd = self.make_git(FakeShell())
        error = git.GitCommandError(['git', 'switch'], 128,
                                    stderr="fatal: a branch named 'existing' already exists\nhint: more")
        with patch('my_git.git.Repo') as fake_repo_cls, patch('builtins.print') as printed:
            fake_repo_cls.return_value.git.switch.side_effect = error
            git_cmd.branch(['existing', 'push'])
        message = printed.call_args[0][0]
        self.assertIn("Branch not created: a branch named 'existing' already exists", message)
        self.assertNotIn('stderr:', message)
        self.assertNotIn('hint', message)
        git_cmd.run.assert_not_called()


class MyGitAddUntrackedTests(unittest.TestCase):
    # Short status with one tracked change and two untracked files, coloured
    # the way 'git -c color.status=always' prints it.
    STATUS = FakeProcess(stdout=b' M tracked.py\n\x1b[31m??\x1b[m new.py\n\x1b[31m??\x1b[m docs/notes.md\n')
    NO_UNTRACKED = FakeProcess(stdout=b' M tracked.py\n')
    NOOP = FakeProcess()

    def make_git(self, shell, answers=(), select=None):
        return with_shell(MyGit([], {}, '/fake/repo', '/fake/logs',
                                prompt=queued_prompt(*answers),
                                select=select or queued_select(1)), shell)

    def commands_run(self, shell):
        return [call[0][0] for call in shell.calls]

    def test_lists_only_untracked_files(self):
        shell = FakeShell([self.STATUS])
        untracked = git_with(shell).get_untracked_changes()
        self.assertEqual([c['path'] for c in untracked], ['new.py', 'docs/notes.md'])

    def test_add_shows_the_selected_file_then_adds_it(self):
        for key in ['a', 'A', 's', 'S']:
            with self.subTest(key=key):
                shell = FakeShell([self.STATUS, self.NOOP])
                with patch('builtins.print'):
                    self.make_git(shell, [key]).add_untracked([])
                run = self.commands_run(shell)
                self.assertIn(['git', 'diff', '--no-index', '--', '/dev/null', 'docs/notes.md'], run)
                self.assertIn(['git', 'add', '--', 'docs/notes.md'], run)

    def test_undo_deletes_the_file(self):
        shell = FakeShell([self.STATUS, self.NOOP])
        with patch('builtins.print'):
            self.make_git(shell, ['u']).add_untracked([])
        run = self.commands_run(shell)
        self.assertIn(['rm', '--', 'docs/notes.md'], run)
        self.assertNotIn(['git', 'add', '--', 'docs/notes.md'], run)


    def test_r_and_d_refresh_the_file_without_deleting_it(self):
        for key in ['r', 'R', 'd', 'D']:
            with self.subTest(key=key):
                shell = FakeShell([self.STATUS, self.NOOP])
                with patch('builtins.print'):
                    self.make_git(shell, [key, 'c']).add_untracked([])
                run = self.commands_run(shell)
                shows = [c for c in run if c[:3] == ['git', 'diff', '--no-index']]
                self.assertEqual(len(shows), 2)
                self.assertNotIn(['rm', '--', 'docs/notes.md'], run)

    def test_cancel_changes_nothing(self):
        shell = FakeShell([self.STATUS, self.NOOP])
        with patch('builtins.print'):
            self.make_git(shell, ['c']).add_untracked([])
        run = self.commands_run(shell)
        self.assertFalse(any(c[:2] == ['git', 'add'] or c[:1] == ['rm'] for c in run))

    def test_nothing_untracked_does_not_ask(self):
        def select(items):
            raise AssertionError('select() should not be called')
        shell = FakeShell([self.NO_UNTRACKED])
        git_cmd = self.make_git(shell, select=select)
        git_cmd.run = MagicMock()
        with patch('builtins.print'):
            git_cmd.add_untracked(['status'])
        git_cmd.run.assert_called_once_with(['status'])

    def test_escape_from_the_list_does_nothing(self):
        shell = FakeShell([self.STATUS])
        git_cmd = self.make_git(shell, select=queued_select(None))
        git_cmd.run = MagicMock()
        with patch('builtins.print'):
            git_cmd.add_untracked(['status'])
        self.assertEqual(len(shell.calls), 1)
        git_cmd.run.assert_called_once_with(['status'])


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
        git_cmd = with_shell(MyGit([], {}, self.work, '/fake/logs',
                        prompt=queued_prompt()), FakeShell())
        status = git_cmd.checkout_in_folder('ABC-123-extra', self.work)
        self.assertEqual(status, 0)
        self.assertEqual(self.current_branch(), 'feature/ABC-123-extra')

    def test_selects_and_checks_out_the_chosen_branch_on_multiple_matches(self):
        offered = []

        def select(items):
            offered.append(items)
            return 1

        git_cmd = with_shell(MyGit([], {}, self.work, '/fake/logs',
                        prompt=queued_prompt(), select=select), FakeShell())
        git_cmd.checkout_in_folder('ABC-123', self.work)
        self.assertEqual(offered, [['feature/ABC-123', 'feature/ABC-123-extra']])
        self.assertEqual(self.current_branch(), 'feature/ABC-123-extra')

    def test_escape_from_the_branch_list_checks_out_nothing(self):
        git_cmd = with_shell(MyGit([], {}, self.work, '/fake/logs',
                        prompt=queued_prompt(), select=queued_select(None)), FakeShell())
        with patch('builtins.print'), self.assertRaises(SystemExit):
            git_cmd.checkout_in_folder('ABC-123', self.work)
        self.assertEqual(self.current_branch(), 'main')

    def test_checks_out_main_directly_regardless_of_match_content(self):
        run_git('checkout', '-q', '-b', 'feature/ABC-123', 'origin/feature/ABC-123', cwd=self.work)
        self.assertEqual(self.current_branch(), 'feature/ABC-123')

        git_cmd = with_shell(MyGit([], {}, self.work, '/fake/logs',
                        prompt=queued_prompt()), FakeShell())
        git_cmd.checkout_in_folder('main', self.work)
        self.assertEqual(self.current_branch(), 'main')

    def test_checks_out_a_local_only_branch(self):
        run_git('checkout', '-q', '-b', 'feature/XYZ-999', 'origin/main', cwd=self.work)
        run_git('checkout', '-q', 'main', cwd=self.work)

        git_cmd = with_shell(MyGit([], {}, self.work, '/fake/logs',
                        prompt=queued_prompt()), FakeShell())
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
        git_cmd = with_shell(MyGit([], {}, self.work_dir, '/fake/logs',
                        prompt=queued_prompt()), FakeShell())
        git_cmd.work(['ABC-123'])

        worktree_path = os.path.join(self.work_dir, '.worktrees', 'ABC-123')
        self.assertTrue(os.path.isdir(worktree_path))

        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                cwd=worktree_path, check=True, capture_output=True)
        self.assertEqual(result.stdout.decode('UTF-8').strip(), 'feature/ABC-123')


def git_with(shell):
    return with_shell(MyGit([], {}, '/fake/repo', '/fake/logs', prompt=queued_prompt()), shell)


class MyStatusHelperTests(unittest.TestCase):
    def test_popen_splits_and_drops_blank_lines(self):
        shell = FakeShell([FakeProcess(stdout=b'foo\n\nbar\n')])
        self.assertEqual(git_with(shell).popen(['git', 'status']), ['foo', 'bar'])

    def test_popen_strips_each_line_consistently(self):
        # Regression test: popen() used to strip() the whole blob before
        # splitting on newlines, so only the first line's leading space
        # was removed and every later line kept theirs.
        shell = FakeShell([FakeProcess(stdout=b' foo\n bar\n')])
        self.assertEqual(git_with(shell).popen(['git', 'status']), ['foo', 'bar'])

    def test_get_all_changes_parses_short_status_output(self):
        shell = FakeShell([FakeProcess(stdout=b' M foo.py\nA  bar.py\n')])
        changes = git_with(shell).get_all_changes()
        self.assertEqual([c['path'] for c in changes], ['foo.py', 'bar.py'])

    def test_get_all_changes_pretty_formatting_is_consistent_across_lines(self):
        # Regression test for the "my git review" bug: the first unstaged
        # change was missing its leading space relative to later ones.
        shell = FakeShell([FakeProcess(
            stdout=b' M My/my_git.py\n M My/my_gradle.py\n M My/my_harness.py\n')])
        changes = git_with(shell).get_all_changes()
        self.assertEqual(
            [c['pretty'] for c in changes],
            ['M My/my_git.py', 'M My/my_gradle.py', 'M My/my_harness.py'])

    def test_get_unstaged_changes_filters_by_diff_files(self):
        shell = FakeShell([
            FakeProcess(stdout=b' M foo.py\nA  bar.py\n'),
            FakeProcess(stdout=b':100644 100644 aaa bbb M\tfoo.py\n'),
        ])
        unstaged = git_with(shell).get_unstaged_changes()
        self.assertEqual([c['path'] for c in unstaged], ['foo.py'])

    def test_get_all_changes_uses_destination_path_for_renames(self):
        shell = FakeShell([FakeProcess(stdout=b'RM old/Foo.java -> new/FooImpl.java\n M bar.py\n')])
        changes = git_with(shell).get_all_changes()
        self.assertEqual([c['path'] for c in changes], ['new/FooImpl.java', 'bar.py'])

    def test_get_all_changes_uses_destination_path_for_coloured_renames(self):
        shell = FakeShell([FakeProcess(
            stdout=b'\x1b[32mR\x1b[m\x1b[31mM\x1b[m old/Foo.java -> new/FooImpl.java\n')])
        changes = git_with(shell).get_all_changes()
        self.assertEqual([c['path'] for c in changes], ['new/FooImpl.java'])

    def test_get_unstaged_changes_matches_renamed_file_with_unstaged_edits(self):
        # Regression test: a staged rename with further unstaged edits used to
        # be keyed by its old path, so it never matched diff-files' new path.
        shell = FakeShell([
            FakeProcess(stdout=b'RM old/Foo.java -> new/FooImpl.java\n M bar.py\n'),
            FakeProcess(stdout=b':100644 100644 aaa bbb M\tnew/FooImpl.java\n'
                               b':100644 100644 ccc ddd M\tbar.py\n'),
        ])
        unstaged = git_with(shell).get_unstaged_changes()
        self.assertEqual([c['path'] for c in unstaged], ['new/FooImpl.java', 'bar.py'])
        self.assertEqual(unstaged[0]['pretty'], 'RM old/Foo.java -> new/FooImpl.java')

    def test_get_unstaged_changes_falls_back_to_path_dicts_when_unmatched(self):
        # Regression test: the fallback used to return bare strings, so callers
        # reading change['pretty'] crashed with a TypeError.
        shell = FakeShell([
            FakeProcess(stdout=b' M foo.py\n'),
            FakeProcess(stdout=b':100644 100644 aaa bbb M\tfoo.py\n'
                               b':100644 100644 ccc ddd M\tmystery.py\n'),
        ])
        with patch('builtins.print'):
            unstaged = git_with(shell).get_unstaged_changes()
        self.assertEqual(unstaged, [
            {'path': 'foo.py', 'pretty': 'foo.py'},
            {'path': 'mystery.py', 'pretty': 'mystery.py'},
        ])

    def test_show_status_reports_false_when_no_changes(self):
        shell = FakeShell([FakeProcess(stdout=b'')])
        self.assertFalse(git_with(shell).show_status())


if __name__ == '__main__':
    unittest.main()
