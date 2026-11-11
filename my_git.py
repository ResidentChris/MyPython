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

MAIN_BRANCH = 'main'


def default_select(items):
    choices = [questionary.Choice(title=ANSI(item).__pt_formatted_text__(), value=i)
               for i, item in enumerate(items)]
    choices.append(questionary.Separator(" "))
    question = questionary.select("", choices=choices)

    @question.application.key_bindings.add(Keys.Escape, eager=True)
    def _cancel(event):
        event.app.exit(result=None)

    return question.ask()


class MyGit:
    def __init__(self, commands, arguments, repositories, logs, shell=subprocess.Popen,
                 prompt=input, select=default_select):
        self.repositories = repositories
        self.shell = shell
        self.prompt = prompt
        self.select = select
        self.descriptions = dict([
            ('pull', 'Pull the latest changes from origin'),
            ('push', 'Force-push the current branch to origin (--force-with-lease)'),
            ('review', 'Interactively review, stage, or revert unstaged changes'),
            ('status', 'Show the current git status'),
            ('checkout', 'Check out the branch matching a ticket ID (or "main")'),
            ('work', 'Create a git worktree for a ticket in .worktrees/'),
            ('commit', 'Commit the currently staged ticket file, pre-filled with its ticket ID'),
        ])

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "pull":
                self.pull(commands)

            elif command == "push":
                self.push(commands)

            elif command == "review":
                self.diff(commands)

            elif command == "status":
                self.status(commands)

            elif len(commands) >= 1 and command == "checkout":
                self.checkout(commands)

            elif len(commands) >= 1 and command == "work":
                self.work(commands)

            elif command == "commit":
                self.commit(commands)

            elif command == "help" or command == "-h" or command == "--help":
                self.help(commands)

            else:
                commands.insert(0, command)

    def pull(self, commands):
        git.Repo(self.repositories).remotes.origin.pull()
        self.run(commands)

    def push(self, commands):
        self.shell(["git", "push", "--force-with-lease"], cwd=self.repositories).wait()
        self.run(commands)

    def diff(self, commands):
        if len(commands) == 0:
            if not my_status(self.shell, print_selection_list=False):
                exit()
            changes = get_unstaged_changes(shell=self.shell)
            index = self.select([change['pretty'] for change in changes])
            if index is None:
                self.run(commands)
                return
            strIndex = str(index + 1)
        else:
            strIndex = commands.pop(0)

        self.shell("clear")

        try:
            index = int(strIndex) - 1
            changes = get_unstaged_changes(shell=self.shell)
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
        print("%s? [C]" % Options(['Stage', Colour.GREEN], ['Revert', Colour.RED], ['Diff again', Colour.BLUE], ['Cancel', Colour.CLEAR]), end=" ")
        response = self.prompt()
        if response.upper() == "D":
            commands.insert(0, strIndex)
            self.diff(commands)
        else:
            if response.upper() == "S":
                stage = self.shell(["git", "stage", "--", file])
                stage.wait()
                print(Colour.GREEN.value, "Staged", file, Colour.CLEAR.value)
            elif response.upper() == "R":
                checkout = self.shell(["git", "checkout", "--", file])
                checkout.wait()
                print(Colour.RED.value, "Reverted", file, Colour.CLEAR.value)
            else:
                print("Cancelled.")

            self.status(commands)

    def status(self, commands):
        my_status(self.shell)
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
        branches = repo.git.branch('-a')
        for ticket in ticketList.split(","):
            branch = self.resolve_branch(ticket, branches)
            if ticket != MAIN_BRANCH:
                break
        repo.git.checkout(branch)
        return 0

    def resolve_branch(self, ticket, branches):
        remote_matches = re.findall("(?:remotes/)?origin/([^\\s]*%s[^\\s]*)" % ticket,
                             branches,
                             flags=re.IGNORECASE)
        local_matches = re.findall("^\\*?\\s*(?!(?:remotes/)?origin/)([^\\s]*%s[^\\s]*)" % ticket,
                             branches,
                             flags=re.IGNORECASE | re.MULTILINE)
        matches = list(dict.fromkeys(remote_matches + local_matches))
        if len(matches) == 0:
            print("%sCheckout: No matching branch found.%s" % (Colour.RED.value, Colour.CLEAR.value))
            exit(1)

        if ticket == MAIN_BRANCH:
            return MAIN_BRANCH
        elif len(matches) == 1:
            return matches[0]
        else:
            for i in range(len(matches)):
                print("[%d] %s" % (i + 1, matches[i]))
            response = self.prompt("? ")
            return matches[int(response) - 1]

    def work(self, commands):
        ticket = commands.pop(0)
        repo = git.Repo(self.repositories)
        branches = repo.git.branch('-r')
        branch = self.resolve_branch(ticket, branches)

        worktrees_dir = os.path.join(self.repositories, '.worktrees')
        os.makedirs(worktrees_dir, exist_ok=True)
        path = os.path.join(worktrees_dir, ticket)

        repo.git.worktree('add', path, branch)
        self.run(commands)

    def commit(self, commands):
        status = self.shell(["git", "status", "--porcelain"],
                            stdout=subprocess.PIPE)
        edits = status.communicate()[0].decode('UTF-8').strip().split('\n')
        if len(edits) == 1:
            filename = edits[0].split(' ')[-1]
            ticket_id = filename.split('_')[0]
            file = open('%s/Tickets/.git/COMMIT_EDITMSG' % self.repositories,
                        'w+')
            for line in [
                    '%s ' % ticket_id,
                    '',
                    '# You know the drill.',
            ]:
                file.write('%s\n' % line)
            file.close()
            commit = self.shell(['git', 'commit'])
            commit.wait()
        self.run(commands)

    def help(self, commands):
        if len(commands) >= 1 and commands[0] in self.descriptions:
            command = commands.pop(0)
            print('    %-10s %s' % (command, self.descriptions[command]))
            self.run(commands)
        else:
            print('Possible commands are:')
            for command, description in self.descriptions.items():
                print('    %-10s %s' % (command, description))


def my_status(shell=subprocess.Popen, print_selection_list=True):
    changes = get_all_changes(shell)
    print()

    number_of_changes = len(changes)
    if number_of_changes == 0:
        print("No changes.\n")
        return False

    for change in changes:
        print(change['pretty'])
    print('%d changes.\n' % number_of_changes)

    unstaged_changes = get_unstaged_changes(changes, shell)
    if len(unstaged_changes) == 0:
        print("No unstaged changes.\n")
        return False

    if print_selection_list:
        for i, change in enumerate(unstaged_changes):
            print("[%d] %s" % (i + 1, change['pretty']))
        print()

    return True


def get_all_changes(shell=subprocess.Popen):
    changes = popen(['git', '-c', 'color.status=always', 'status', '--short'], shell)
    return [{'path': change.split()[1], 'pretty': change} for change in changes]


def get_unstaged_changes(all_changes = None, shell=subprocess.Popen):
    all_changes = all_changes or get_all_changes(shell)
    unstaged_changes = list(dict.fromkeys(
        change.strip().split()[5] for change in popen(['git', 'diff-files'], shell)))

    unstaged_changes_pretty = [change for change in all_changes if change['path'] in unstaged_changes]
    if len(unstaged_changes_pretty) == len(unstaged_changes):
        unstaged_changes = unstaged_changes_pretty
    else:
        print("%sWarning%s: couldn't find pretty entries for all unstaged changes, displaying path only.\n" % (Colour.YELLOW.value, Colour.CLEAR.value))

    return unstaged_changes


def popen(command, shell=subprocess.Popen):
    output = shell(command, stdout=subprocess.PIPE).communicate()[0].decode('UTF-8')
    return [line.strip() for line in output.split('\n') if len(line.strip()) > 0]
