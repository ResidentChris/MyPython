#!/usr/bin/env python

import os
import re
import subprocess
import time
from sys import exit
from my_colours import Colour
from my_colours import Options
from my_module import MyAbstractModule

class MyHarness(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'harness'

    @classmethod
    def description(cls):
        return 'Run the web, iOS, or Android test harness'

    def __init__(self, commands, arguments, repositories, logs):
        self.repositories = repositories
        self.folder = arguments['harness']['folder']
        self.url = arguments['harness']['url']
        self.descriptions = dict([
            ('web', 'Run or build the web test harness (in %s)' % self.folder),
            ('ios', 'Run the iOS harness (not implemented yet)'),
            ('android', 'Run the Android harness (not implemented yet)'),
        ])

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "web":
                self.web(commands)

            elif command == "ios":
                self.ios(commands)

            elif command == "android":
                self.android(commands)

            elif self.is_help(command):
                self.help(commands)

            else:
                commands.insert(0, command)

    def web(self, commands):
        # 'web' on its own, or followed by anything but build/run, means 'web run'.
        if len(commands) == 0 or commands[0] not in ("build", "run"):
            commands.insert(0, "run")
        while len(commands) >= 1 and commands[0] in ("build", "run"):
            if commands.pop(0) == "build":
                self.web_build()
            else:
                self.web_run()
        self.run(commands)

    def web_run(self):
        test_harness = self.start_web_harness()
        wait(test_harness, "compiled successfully")

        chromium = self.start_chromium()

        try:
            test_harness.wait()
        except KeyboardInterrupt:
            print("Web harness interrupted.")
            chromium.kill()

    def web_build(self):
        self.shell(["npm", "install"], cwd=self.folder).wait()

    def ios(self, commands):
        print("The iOS harness is not implemented yet.")
        self.run(commands)

    def android(self, commands):
        print("The Android harness is not implemented yet.")
        self.run(commands)

    def start_web_harness(self):
        print(" ")
        print("###########################")
        print("# Starting web harness... #")
        print("###########################")
        print(" ")
        return self.shell(
            ["npm", "run", "harness:web"],
            cwd=self.folder,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "FORCE_COLOR": "1"},
        )

    def start_chromium(self):
        print(" ")
        print("########################")
        print("# Starting Chromium... #")
        print("########################")
        print(" ")
        return self.shell([
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "--args",
            "--user-data-dir=/tmp/chrome_dev_test",
            "--disable-web-security",
            "--ignore-certificate-errors",
            "--use-mock-keychain",
            self.url
        ])


def wait(process, text):
    ansi_escape = re.compile(r'\033\[[0-9;]*m')
    assert process.stdout is not None
    for line in process.stdout:
            print(line, end="")
            if "compiled successfully" in ansi_escape.sub("", line).lower():
                break
