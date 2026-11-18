#!/usr/bin/env python

import os
from my_module import MyAbstractModule
from shutil import rmtree


class MyNpm(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'npm'

    @classmethod
    def description(cls):
        return 'Clean or start the npm project'

    def __init__(self, commands, arguments, repositories, logs, prompt=input):
        self.prompt = prompt
        self.descriptions = {
            'clean': 'Delete node_modules and run npm install',
            'start': 'Run npm start',
        }

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "clean":
                self.clean(commands)

            elif command == "start":
                self.start(commands)

            elif self.is_help(command):
                self.help(commands)

            else:
                commands.insert(0, command)

    def clean(self, commands):
        node_modules = os.path.join(os.getcwd(), 'node_modules')
        if os.path.isdir(node_modules):
            print('Deleting node_modules...', end=' ')
            rmtree(node_modules)
            print('done.')
        self.shell(['npm', 'install'], cwd=os.getcwd()).wait()
        self.run(commands)

    def start(self, commands):
        self.shell(['npm', 'run', 'start'], cwd=os.getcwd()).wait()
        self.run(commands)
