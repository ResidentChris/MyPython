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

    while len(commands) >= 1:
        command = commands.pop(0)
        if command == '-h' or command == '--help' or command == 'help':
            print('My (Python)')
            if len(commands) >= 1 and commands[0] in modules:
                next_command = commands.pop(0)
                print('    %-10s %s' % (next_command, modules[next_command].description()))
            else:
                print('Possible commands are:')
                for name, module in modules.items():
                    print('    %-10s %s' % (name, module.description()))
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
