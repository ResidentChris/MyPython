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

ROOT = '/path/to/repositories'
REPOSITORY = os.getcwd()
LOGS = '%s/logs' % ROOT

if __name__ == "__main__":
    # Initialise colorama
    init()

    commands = sys.argv[1:]

    arguments = {
        'git': {
            'repos': {
                'Backend': '%s/Backend' % REPOSITORY,
                'FrontEnd': '%s/FrontEnd' % REPOSITORY,
            },
        },
        # gradle's deploy() reads tomcat_webapps from this even though the
        # tomcat command itself is deprecated; left blank until it's needed.
        'tomcat': {
            'tomcat_home': '',
        },
        'gradle': {
            # Webapps built by the Backend repo, in deployment order. 'module'
            # is the folder under Backend, 'project' the Gradle subproject.
            'webapps': [
                {
                    'abbreviation': 'A1',
                    'name': 'Webapp One',
                    'module': 'Webapp-One',
                    'project': 'webapp_one',
                    'war': 'webapp_one.war',
                },
                {
                    'abbreviation': 'A2',
                    'name': 'Webapp Two',
                    'module': 'Webapp-Two',
                    'project': 'webapp_two',
                    'war': 'webapp_two.war',
                },
            ],
        },
        'harness': {
            'folder': '%s/example-sdk/react/library' % ROOT,
            'url': 'https://localhost.example.com:8080',
        },
        'npm': {
            'wsl_user': 'your_wsl_user',
            'environment': {
                'APP_ONE_URL': 'http://localhost:9999',
                'APP_TWO_URL': 'http://localhost:9999',
            },
        },
        'qmk': {
            'folder': '/path/to/qmk_firmware',
            'keyboard': 'keebio/iris/rev5',
            'keymap': 'ColemakForMac'
        },
        'xc': {
            'folder': '%s/example-sdk' % ROOT,
            'workspace': 'ios/library/test-harness/ExampleSdk.xcworkspace',
            'scheme': 'ExampleSdk-Unit-Tests',
        },
    }

    # TODO: Temporary fix. Only the My* command classes are kept; other
    # imported classes (e.g. Colour) would otherwise show up in help as bogus
    # commands like 'lour'. Replace with a more robust approach, e.g. an
    # explicit registry of command classes instead of discovering every class
    # imported into this module by name.
    classes = [
        member for member in inspect.getmembers(sys.modules[__name__], inspect.isclass)
        if member[0].startswith('My')
    ]

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
                for clazz in classes:
                    name = clazz[0][2:].lower()
                    print('    %-10s %s' % (name, descriptions.get(name, '')))
        else:
            matches = [
                candidate[1] for candidate in classes
                if candidate[1].__name__.lower() == 'my%s' % command.lower()
            ]
            if len(matches) > 0:
                matches[0].__call__(commands, arguments, REPOSITORY,
                                    LOGS).run(commands)
            else:
                print("%sUnknown command: %s%s" % (Colour.RED.value, command, Colour.CLEAR.value))
                break
