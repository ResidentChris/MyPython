#!/usr/bin/env python3

from my_git import MyGit
from my_gradle import MyGradle
from my_harness import MyHarness
from my_npm import MyNpm
from my_qmk import MyQmk
from my_xc import MyXc

import inspect
import os
import sys
from colorama import init
from my_colours import Colour
from my_module import MyModule, find_modules
from my_settings import MissingSettings, load_settings

REPOSITORY = os.getcwd()


def command_modules() -> dict[str, type[MyModule]]:
    """Every command module imported into this file, keyed by its command."""
    classes = [cls for _, cls in inspect.getmembers(sys.modules[__name__], inspect.isclass)]
    return {cls.command(): cls for cls in find_modules(classes)}


if __name__ == "__main__":
    # Initialise colorama
    init()

    commands = sys.argv[1:]

    modules = command_modules()

    descriptions: dict[str, str] = {
        'git': 'Pull, push, review, checkout, or commit changes',
        'gradle': 'Build, format, deploy, or inspect dependencies via Gradle',
        'harness': 'Run the web, iOS, or Android test harness',
        'npm': 'Clean or start the npm project',
        'qmk': 'Compile or flash QMK keyboard firmware',
        'xc': 'Run xcodebuild commands (test)',
    }

    while len(commands) >= 1:
        command = commands.pop(0)
        if command == '-h' or command == '--help' or command == 'help':
            print('My (Python)')
            if len(commands) >= 1 and commands[0] in descriptions:
                next_command = commands.pop(0)
                print('    %-10s %s' % (next_command, descriptions[next_command]))
            else:
                print('Possible commands are:')
                for name in modules:
                    print('    %-10s %s' % (name, descriptions.get(name, '')))
        else:
            module = modules.get(command.lower())
            if module is not None:
                try:
                    arguments = load_settings(REPOSITORY)
                except MissingSettings as e:
                    print('%s%s%s' % (Colour.RED.value, e, Colour.CLEAR.value))
                    sys.exit(1)
                logs = '%s/logs' % arguments['root']
                module(commands, arguments, REPOSITORY, logs).run(commands)
            else:
                print("%sUnknown command: %s%s" % (Colour.RED.value, command, Colour.CLEAR.value))
                break
