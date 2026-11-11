#!/usr/bin/env python

import subprocess
from shutil import rmtree


class MyNpm:
    def __init__(self, commands, arguments, repositories, logs, shell=subprocess.Popen, prompt=input):
        self.repo = arguments['git']['repos']['FrontEnd']
        self.node_modules = '%s/node_modules' % self.repo
        self.wsl_user = arguments['npm']['wsl_user']
        self.environment = arguments['npm']['environment']
        self.shell = shell
        self.prompt = prompt

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "clean":
                self.clean(commands)

            elif command == "start":
                self.start(commands)

            else:
                commands.insert(0, command)

    def clean(self, commands):
        print('Deleting node_modules...', end=' ')
        rmtree(self.node_modules)
        print('done.')
        npm_install = self.shell(
            ['wsl', '--user', self.wsl_user, '--cd', self.repo, 'npm', 'install'])
        npm_install.wait()
        self.run(commands)

    def start(self, commands):
        exports = []
        for name, value in self.environment.items():
            exports += ['export', '%s=%s;' % (name, value)]
        proc = self.shell(
            ['wsl', '--user', self.wsl_user, '--cd', self.repo]
            + exports
            + ['~/.nvm/versions/node/v16.13.0/bin/npm', 'run', 'start']
        )
        proc.wait()
        self.run(commands)
