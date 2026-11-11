#!/usr/bin/env python

import subprocess

DESTINATION = 'platform=iOS Simulator,name=iPhone 17'


class MyXc:
    def __init__(self, commands, arguments, repositories, logs):
        self.folder = arguments['xc']['folder']
        self.workspace = arguments['xc']['workspace']
        self.scheme = arguments['xc']['scheme']
        self.descriptions = dict([
            ('test', "Run the iOS unit tests (xcodebuild test -workspace %s -scheme %s -destination '%s')" %
             (self.workspace, self.scheme, DESTINATION)),
        ])

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "test":
                self.test(commands)

            elif command == "help" or command == "-h" or command == "--help":
                self.help(commands)

            else:
                commands.insert(0, command)

    def test(self, commands):
        subprocess.Popen([
            "xcodebuild", "test",
            "-workspace", self.workspace,
            "-scheme", self.scheme,
            "-destination", DESTINATION,
        ], cwd=self.folder).wait()
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
