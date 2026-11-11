#!/usr/bin/env python

import subprocess


class MyQmk:
    def __init__(self, commands, arguments, repositories, logs):
        self.folder = arguments['qmk']['folder']
        self.keyboard = arguments['qmk']['keyboard']
        self.keymap = arguments['qmk']['keymap']
        self.descriptions = dict([
            ('compile', 'Compile the firmware (qmk compile -kb %s -km %s)' %
             (self.keyboard, self.keymap)),
            ('flash', 'Compile and flash the firmware to the connected keyboard (qmk flash -kb %s -km %s)' %
             (self.keyboard, self.keymap)),
        ])

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "compile":
                self.compile(commands)

            elif command == "flash":
                self.flash(commands)

            elif command == "help" or command == "-h" or command == "--help":
                self.help(commands)

            else:
                commands.insert(0, command)

    def compile(self, commands):
        subprocess.Popen(
            ["qmk", "compile", "-kb", self.keyboard, "-km", self.keymap],
            cwd=self.folder).wait()
        self.run(commands)

    def flash(self, commands):
        subprocess.Popen(
            ["qmk", "flash", "-kb", self.keyboard, "-km", self.keymap],
            cwd=self.folder).wait()
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
