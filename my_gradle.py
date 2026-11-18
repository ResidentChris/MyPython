#!/usr/bin/env python

import os
import sys
from time import time
from my_colours import Colour
from my_module import MyAbstractModule


class MyGradle(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'gradle'

    @classmethod
    def description(cls):
        return 'Build, test, format, or publish via Gradle'

    def __init__(self, commands, arguments, repositories, logs, prompt=input):
        self.prompt = prompt
        self.descriptions = {
            'clean': 'Run ./gradlew clean',
            'format': 'Run ./gradlew format',
            'test': 'Run ./gradlew test, stopping if the tests fail',
            'build': 'Run ./gradlew build (add "quickly" to skip tests)',
            'install': 'Alias for build',
            'assemble': 'Run ./gradlew assemble, skipping tests',
            'publish': 'Run ./gradlew publishToMavenLocal, stopping if it fails',
        }
        print('Running Gradle in %s.' % os.getcwd())

    def gradlew(self, directory):
        if not os.path.isfile(os.path.join(directory, 'gradlew')):
            print('%sNo Gradle wrapper (gradlew) found in %s.%s Run this from a directory that contains gradlew.'
                  % (Colour.RED.value, directory, Colour.CLEAR.value))
            sys.exit(1)
        return './gradlew'

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "clean":
                self.clean(commands)

            elif command == "format":
                self.format(commands)

            elif command == "test":
                self.test(commands)

            elif command == 'build' or command == "install":
                self.build(commands)

            elif command == 'assemble':
                self.build(commands, True)

            elif command == "publish":
                self.publish(commands)

            elif self.is_help(command):
                self.help(commands)

            else:
                commands.insert(0, command)

    def clean(self, commands):
        cwd = self.shell([self.gradlew(os.getcwd()), "clean"], cwd=os.getcwd())
        cwd.wait()
        self.run(commands)

    def test(self, commands):
        cwd = self.shell([self.gradlew(os.getcwd()), 'test'], cwd=os.getcwd())
        status = cwd.wait()
        if status != 0:
            print('Tests %sfailed%s.' % (Colour.RED.value, Colour.CLEAR.value))
            sys.exit(status)
        self.run(commands)

    def publish(self, commands):
        cwd = self.shell([self.gradlew(os.getcwd()), 'publishToMavenLocal'], cwd=os.getcwd())
        status = cwd.wait()
        if status != 0:
            print('Publish to Maven Local %sfailed%s.' % (Colour.RED.value, Colour.CLEAR.value))
            sys.exit(status)
        self.run(commands)

    def format(self, commands):
        cwd = self.shell([self.gradlew(os.getcwd()), 'format'], cwd=os.getcwd())
        cwd.wait()
        self.run(commands)

    def build(self, commands, skip_tests = False):
        if len(commands) > 0 and commands[0] == 'quickly':
            commands.pop(0)
            skip_tests = True
        
        if skip_tests:
            print(
                '                             %sSKIPPING TESTS%s                             '
                % (Colour.RED.value, Colour.CLEAR.value)
            )
        else:
            print(
                '                             %sRunning tests%s                              '
                % (Colour.GREEN.value, Colour.CLEAR.value)
            )

        build_commands = [self.gradlew(os.getcwd()), 'assemble' if skip_tests else 'build']

        print("Building %s..." % os.path.basename(os.getcwd()))

        cwd_start = time()
        cwd = self.shell(build_commands,
                         cwd=os.getcwd())
        cwd_status = cwd.wait()
        if cwd_status != 0:
            print("Build %sfailed%s." % (Colour.RED.value, Colour.CLEAR.value))
            print('Continue anyway? [y/N]')
            response = self.prompt()
            if response.upper() == 'Y':
                self.run(commands)
            else:
                exit()
        else:
            print("Build %ssucceeded%s in %d s." %
                  (Colour.GREEN.value, Colour.CLEAR.value, time() - cwd_start))
        if cwd_status == 0:
            self.run(commands)
