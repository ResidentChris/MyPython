#!/usr/bin/env python

import git
import os
import questionary
import re
import subprocess
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.keys import Keys
from sys import exit
from my_colours import Colour
from my_colours import Options
from my_module import MyAbstractModule

MAIN_BRANCH = 'main'
ANSI_ESCAPE = re.compile(r'\033\[[0-9;]*m')


# Returned by a select when the user asks for the list to be refreshed.
REFRESH = 'refresh'
REFRESH_KEYS = ('r', 'R', 'd', 'D')


def default_select(items):
    choices = [questionary.Choice(title=ANSI(item).__pt_formatted_text__(), value=i)
               for i, item in enumerate(items)]
    choices.append(questionary.Separator(" "))
    question = questionary.select("", choices=choices, instruction="(Use arrow keys, r to refresh)")
    bindings = question.application.key_bindings

    @bindings.add(Keys.Escape, eager=True)
    def _cancel(event):
        event.app.exit(result=None)

    for key in REFRESH_KEYS:
        bindings.add(key, eager=True)(lambda event: event.app.exit(result=REFRESH))

    return question.ask()


def git_error(error):
    """git's message from a GitCommandError, without GitPython's wrapping or git's hints."""
    message = error.stderr.strip()
    if message.startswith("stderr: '") and message.endswith("'"):
        message = message[len("stderr: '"):-1]
    lines = [line.removeprefix('fatal: ').removeprefix('error: ')
             for line in message.splitlines() if line.strip() and not line.startswith('hint:')]
    return '\n'.join(lines) if lines else 'exit code %s' % error.status


def describe_failure(error):
    """A human-readable message for a GitPython error."""
    if isinstance(error, git.GitCommandError):
        command = ' '.join(str(part) for part in error.command) if isinstance(error.command, list) else error.command
        return '%s failed: %s' % (command, git_error(error))
    if isinstance(error, git.NoSuchPathError):
        return 'No such folder: %s' % error
    if isinstance(error, git.InvalidGitRepositoryError):
        return 'Not a git repository: %s' % error
    return 'Git failed: %s' % error


class MyGit(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'git'

    @classmethod
    def description(cls):
        return 'Pull, push, review, add, checkout, or create branches'

    def __init__(self, commands, arguments, repositories, logs,
                 prompt=input, select=default_select):
        self.repositories = repositories
        self.prompt = prompt
        self.select = select
        self.descriptions = {
            'pull': 'Pull the latest changes from origin',
            'push': 'Force-push the current branch to origin (--force-with-lease; add "up" to set its upstream)',
            'review': 'Pick an unstaged change to view, then add or undo it',
            'add': 'Pick an untracked file to view, then add or undo (delete) it',
            'stage': 'Alias for add',
            'status': 'Show the current git status',
            'checkout': 'Check out the branch matching a ticket ID (or "main")',
            'work': 'Create a git worktree for a ticket in .worktrees/',
            'branch': 'Create a branch and switch to it ("list" or "--list" lists branches)',
        }

    def run(self, commands):
        try:
            self.dispatch(commands)
        except git.GitError as e:
            print("%s%s%s" % (Colour.RED.value, describe_failure(e), Colour.CLEAR.value))
            exit(1)

    def dispatch(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "pull":
                self.pull(commands)

            elif command == "push":
                self.push(commands)

            elif command == "review":
                self.diff(commands)

            elif command in ("add", "stage"):
                self.add_untracked(commands)

            elif command == "status":
                self.status(commands)

            elif len(commands) >= 1 and command == "checkout":
                self.checkout(commands)

            elif len(commands) >= 1 and command == "work":
                self.work(commands)

            elif len(commands) >= 1 and command == "branch":
                self.branch(commands)

            elif self.is_help(command):
                self.help(commands)

            else:
                commands.insert(0, command)

    def pull(self, commands):
        try:
            origin = git.Repo(self.repositories).remote('origin')
        except ValueError:
            print("%sNo remote called 'origin' to pull from.%s" % (Colour.RED.value, Colour.CLEAR.value))
            exit(1)
        origin.pull()
        self.run(commands)

    def push(self, commands):
        command = ["git", "push", "--force-with-lease"]
        if len(commands) > 0 and commands[0] == 'up':
            commands.pop(0)
            command += ["--set-upstream", "origin", "HEAD"]
        self.shell(command, cwd=self.repositories).wait()
        self.run(commands)

    def diff(self, commands):
        if len(commands) == 0:
            def unstaged_changes():
                if not self.show_status(print_selection_list=False):
                    return []
                return self.get_unstaged_changes()

            index, changes = self.choose(unstaged_changes, lambda change: change['pretty'])
            if len(changes) == 0:
                exit()
            if index is None:
                self.run(commands)
                return
            strIndex = str(index + 1)
        else:
            strIndex = commands.pop(0)

        self.shell("clear")

        try:
            index = int(strIndex) - 1
            changes = self.get_unstaged_changes()
            try:
                file = changes[index]['path']
            except IndexError:
                status = self.shell(["git", "status"])
                status.wait()
                print("The index you supplied is out of range.")
                quit(1)
        except ValueError:
            file = strIndex

        # , "--word-diff=color"
        diff = self.shell(["git", "diff", "--", file])
        diff.wait()

        print("\n%s" % file)
        print("%s? [C]" % Options(['Add', Colour.GREEN], ['Undo', Colour.RED], ['Refresh', Colour.BLUE], ['Cancel', Colour.CLEAR]), end=" ")
        response = self.prompt()
        if response.upper() in ("R", "D"):
            commands.insert(0, strIndex)
            self.diff(commands)
        else:
            if response.upper() in ("A", "S"):
                add = self.shell(["git", "add", "--", file])
                add.wait()
                print(Colour.GREEN.value, "Added", file, Colour.CLEAR.value)
            elif response.upper() == "U":
                checkout = self.shell(["git", "checkout", "--", file])
                checkout.wait()
                print(Colour.RED.value, "Reverted", file, Colour.CLEAR.value)
            else:
                print("Cancelled.")

            self.status(commands)

    def add_untracked(self, commands):
        index, untracked = self.choose(self.get_untracked_changes, lambda change: change['pretty'])
        if len(untracked) == 0:
            print("No untracked files.\n")
            self.run(commands)
            return
        if index is None:
            self.run(commands)
            return
        file = untracked[index]['path']

        while True:
            self.shell("clear")
            # Shows the whole file as added lines, and copes with binary files.
            self.shell(["git", "diff", "--no-index", "--", "/dev/null", file]).wait()

            print("\n%s" % file)
            print("%s? [C]" % Options(['Add', Colour.GREEN], ['Undo', Colour.RED], ['Refresh', Colour.BLUE], ['Cancel', Colour.CLEAR]), end=" ")
            response = self.prompt().upper()
            if response not in ("R", "D"):
                break

        if response in ("A", "S"):
            self.shell(["git", "add", "--", file]).wait()
            print(Colour.GREEN.value, "Added", file, Colour.CLEAR.value)
        elif response == "U":
            self.shell(["rm", "--", file]).wait()
            print(Colour.RED.value, "Removed", file, Colour.CLEAR.value)
        else:
            print("Cancelled.")

        self.status(commands)

    def status(self, commands):
        self.show_status()
        self.run(commands)

    def checkout(self, commands):
        ticketList = commands.pop(0)
        status = []
        status.append(self.checkout_in_folder(ticketList, self.repositories))
        if len(list(filter(lambda n: n > 0, status))) > 0:
            print("%sIncomplete checkout.%s" % (Colour.RED.value, Colour.CLEAR.value))
        else:
            self.run(commands)

    def checkout_in_folder(self, ticketList, folder):
        repo = git.Repo(folder)
        for ticket in ticketList.split(","):
            branch = self.resolve_branch(ticket, lambda: repo.git.branch('-a'))
            if ticket != MAIN_BRANCH:
                break
        repo.git.checkout(branch)
        return 0

    def resolve_branch(self, ticket, get_branches):
        def matching_branches():
            branches = get_branches()
            remote_matches = re.findall("(?:remotes/)?origin/([^\\s]*%s[^\\s]*)" % ticket,
                                 branches,
                                 flags=re.IGNORECASE)
            local_matches = re.findall("^\\*?\\s*(?!(?:remotes/)?origin/)([^\\s]*%s[^\\s]*)" % ticket,
                                 branches,
                                 flags=re.IGNORECASE | re.MULTILINE)
            return list(dict.fromkeys(remote_matches + local_matches))

        matches = matching_branches()
        if len(matches) == 0:
            print("%sCheckout: No matching branch found.%s" % (Colour.RED.value, Colour.CLEAR.value))
            exit(1)

        if ticket == MAIN_BRANCH:
            return MAIN_BRANCH
        elif len(matches) == 1:
            return matches[0]
        else:
            index, matches = self.choose(matching_branches, items=matches)
            if index is None:
                print("Cancelled.")
                exit(1)
            return matches[index]

    def choose(self, get_items, label=lambda item: item, items=None):
        """Let the user pick one of get_items() with the arrow keys.

        'r' or 'd' fetches the items again and shows the new list. Returns
        (index, items) for the list the user picked from; index is None if
        they pressed Escape, or if there was nothing to pick from.
        """
        if items is None:
            items = get_items()
        while len(items) > 0:
            index = self.select([label(item) for item in items])
            if index != REFRESH:
                return index, items
            self.shell("clear")
            items = get_items()
        return None, items

    def work(self, commands):
        ticket = commands.pop(0)
        repo = git.Repo(self.repositories)
        branch = self.resolve_branch(ticket, lambda: repo.git.branch('-r'))

        worktrees_dir = os.path.join(self.repositories, '.worktrees')
        os.makedirs(worktrees_dir, exist_ok=True)
        path = os.path.join(worktrees_dir, ticket)

        repo.git.worktree('add', path, branch)
        self.run(commands)

    def branch(self, commands):
        name = commands.pop(0)
        if name in ('list', '--list'):
            # Run git itself rather than listing repo.heads, so the output keeps
            # git's own formatting and colours (e.g. the current branch in green).
            self.shell(["git", "branch", "--list"], cwd=self.repositories).wait()
            self.run(commands)
            return

        try:
            git.Repo(self.repositories).git.switch('-c', name)
        except git.GitCommandError as e:
            print("%sBranch not created: %s%s" % (Colour.RED.value, git_error(e), Colour.CLEAR.value))
            return
        self.run(commands)

    def show_status(self, print_selection_list=True):
        changes = self.get_all_changes()
        print()

        number_of_changes = len(changes)
        if number_of_changes == 0:
            print("No changes.\n")
            return False

        for change in changes:
            print(change['pretty'])
        print('%d changes.\n' % number_of_changes)

        unstaged_changes = self.get_unstaged_changes(changes)
        if len(unstaged_changes) == 0:
            print("No unstaged changes.\n")
            return False

        if print_selection_list:
            for i, change in enumerate(unstaged_changes):
                print("[%d] %s" % (i + 1, change['pretty']))
            print()

        return True

    def get_all_changes(self):
        changes = self.popen(['git', '-c', 'color.status=always', 'status', '--short'])
        # Last token is the destination path, which handles "R  old -> new" renames
        return [{'path': change.split()[-1], 'pretty': change} for change in changes]

    def get_untracked_changes(self):
        lines = self.popen(['git', '-c', 'color.status=always', 'status', '--short', '--untracked-files=all'])
        return [{'path': line.split()[-1], 'pretty': line}
                for line in lines if ANSI_ESCAPE.sub('', line).startswith('??')]

    def get_unstaged_changes(self, all_changes=None):
        all_changes = all_changes or self.get_all_changes()
        unstaged_changes = list(dict.fromkeys(
            change.strip().split()[5] for change in self.popen(['git', 'diff-files'])))

        unstaged_changes_pretty = [change for change in all_changes if change['path'] in unstaged_changes]
        if len(unstaged_changes_pretty) == len(unstaged_changes):
            return unstaged_changes_pretty

        print("%sWarning%s: couldn't find pretty entries for all unstaged changes, displaying path only.\n" % (Colour.YELLOW.value, Colour.CLEAR.value))
        return [{'path': path, 'pretty': path} for path in unstaged_changes]

    def popen(self, command):
        output = self.shell(command, stdout=subprocess.PIPE).communicate()[0].decode('UTF-8')
        return [line.strip() for line in output.split('\n') if len(line.strip()) > 0]
