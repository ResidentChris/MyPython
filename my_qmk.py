#!/usr/bin/env python

from my_module import MyAbstractModule


class MyQmk(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'qmk'

    @classmethod
    def description(cls):
        return 'Compile or flash QMK keyboard firmware'

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

            elif self.is_help(command):
                self.help(commands)

            else:
                commands.insert(0, command)

    def compile(self, commands):
        self.shell(
            ["qmk", "compile", "-kb", self.keyboard, "-km", self.keymap],
            cwd=self.folder).wait()
        self.run(commands)

    def flash(self, commands):
        self.shell(
            ["qmk", "flash", "-kb", self.keyboard, "-km", self.keymap],
            cwd=self.folder).wait()
        self.run(commands)
