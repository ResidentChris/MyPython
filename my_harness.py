#!/usr/bin/env python

import os
import re
import subprocess
import time
from sys import exit
from my_colours import Colour
from my_colours import Options

class MyHarness:
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

            elif command == "help" or command == "-h" or command == "--help":
                self.help(commands)

            else:
                commands.insert(0, command)

    def web(self, commands):
        if len(commands) == 0:
            commands.insert(0, "run")
        elif commands[0] != "run" and commands[0] != "build":
            commands.insert(0, "run")
        self.web_inner(commands)


    def web_inner(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "build":
                self.web_build(commands)
            
            elif command == "run":
                self.web_run(commands)

        self.run(commands)
    
    def web_run(self, commands):
        test_harness = start_web_harness(self.folder)
        wait(test_harness, "compiled successfully")

        chromium = start_chromium(self.url)

        try:
            test_harness.wait()
        except KeyboardInterrupt:
            print("Web harness interrupted.")
            chromium.kill()

        self.web_inner(commands)
    
    def web_build(self, commands):
        subprocess.Popen(["npm", "install"], cwd=self.folder).wait()
        self.web_inner(commands)

    def ios(self, commands):
        print("The iOS harness is not implemented yet.")
        self.run(commands)

    def android(self, commands):
        print("The Android harness is not implemented yet.")
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

def wait(process, text):
    ansi_escape = re.compile(r'\033\[[0-9;]*m')
    assert process.stdout is not None
    for line in process.stdout:
            print(line, end="")
            if "compiled successfully" in ansi_escape.sub("", line).lower():
                break

def start_web_harness(folder):
    print(" ")
    print("###########################")
    print("# Starting web harness... #")
    print("###########################")
    print(" ")
    return subprocess.Popen(
        ["npm", "run", "harness:web"],
        cwd=folder,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "FORCE_COLOR": "1"},
    )

def start_chromium(url):
    print(" ")
    print("########################")
    print("# Starting Chromium... #")
    print("########################")
    print(" ")
    return subprocess.Popen([
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "--args",
        "--user-data-dir=/tmp/chrome_dev_test",
        "--disable-web-security",
        "--ignore-certificate-errors",
        "--use-mock-keychain",
        url
    ])
