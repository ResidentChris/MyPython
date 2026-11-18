#!/usr/bin/env python

import subprocess
from my_module import MyAbstractModule

DESTINATION = 'platform=iOS Simulator,name=iPhone 17'


class MyXc(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'xc'

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

            elif self.is_help(command):
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
