#!/usr/bin/env python

import os
import subprocess
from shutil import copyfile
from time import time
from my_colours import Colour
from my_colours import Options


class MyGradle:
    def __init__(self, commands, arguments, repositories, logs, shell=subprocess.Popen, prompt=input):
        self.repos = arguments['git']['repos']
        self.logs = logs
        self.tomcat_webapps = '%s/Webapps' % arguments['tomcat']['tomcat_home']
        self.webapps = arguments['gradle']['webapps']
        self.shell = shell
        self.prompt = prompt

        self.here = False
        if len(commands) > 0 and commands[0] == 'here':
            commands.pop(0)
            self.here = True
            print('Running Gradle in %s.' % os.getcwd())

    def run(self, commands):
        if len(commands) >= 1:
            command = commands.pop(0)

            if command == "clean":
                self.clean(commands)

            elif command == "format":
                self.format(commands)

            elif command == "install" or command == 'build':
                self.install(commands)

            elif command == 'assemble':
                self.install(commands, True)

            elif command == "deploy":
                self.deploy(commands)

            elif command == "deps":
                self.deps(commands)

            else:
                commands.insert(0, command)

    def clean(self, commands):
        if self.here:
            cwd = self.shell(["gradle", "clean"], cwd=os.getcwd())
            cwd.wait()
        else:
            be = self.shell(["gradle", "clean"],
                            cwd=self.repos['Backend'])
            be.wait()
        self.run(commands)

    def format(self, commands):
        be = self.shell(['gradle', 'format'], cwd=self.repos['Backend'])
        be.wait()
        self.run(commands)

    def install(self, commands, skip_tests = False):
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

        if self.here:
            install_commands = ['gradle', 'assemble' if skip_tests else 'build']

            cwd_log = open("%s/cwd.log" % self.logs, "w")
            print("Installing %s (logging to %s)..." %
                  (os.getcwd().split('\\')[-1], cwd_log.name))

            cwd_start = time()
            cwd = self.shell(install_commands,
                             cwd=os.getcwd())
            cwd_status = cwd.wait()
            cwd_log.close()
            if cwd_status > 0:
                print("Installation %sfailed%s." % (Colour.RED.value, Colour.CLEAR.value))
                print('Continue anyway? [y/N]')
                response = self.prompt()
                if response.upper() == 'Y':
                    self.run(commands)
                else:
                    exit()
            else:
                print("Installation %ssucceeded%s in %d s." %
                      (Colour.GREEN.value, Colour.CLEAR.value, time() - cwd_start))
            if cwd_status == 0:
                self.run(commands)

        else:
            print("Installing Backend")
            be_start = time()
            be_install_commands = ['gradle', 'assemble' if skip_tests else 'build']
            be = self.shell(be_install_commands,
                            cwd=self.repos['Backend'])
            be_status = be.wait()
            if be_status == 0:
                print("BE installation %ssucceeded%s in %d s." %
                      (Colour.GREEN.value, Colour.CLEAR.value, time() - be_start))
                self.run(commands)
            else:
                print("Backend installation %sfailed%s." % (Colour.RED.value, Colour.CLEAR.value))
                if len(commands) == 0:
                    print("\n%s? [A]" % Options(['Retry', Colour.BLUE], ['Abort', Colour.CLEAR]), end=" ")
                else:
                    print("\n%s? [A]" % Options(['Continue', Colour.GREEN], ['Retry', Colour.BLUE], ['Abort', Colour.CLEAR]), end=" ")
                response = self.prompt()
                if response.upper() == 'C':
                    self.run(commands)
                elif response.upper() == 'R':
                    if skip_tests:
                        commands.insert(0, 'quickly')
                    commands.insert(0, 'build')
                    self.run(commands)
                else:
                    exit()

    def deploy(self, commands):
        if self.here:
            cwd = os.getcwd()
            for webapp in self.webapps:
                if cwd.endswith(webapp['module']):
                    print('Deploying %s only.' % webapp['abbreviation'])
                    self.deploy_webapp(webapp)
                    break
        else:
            print('Deploying %s.' % ' and '.join(w['abbreviation'] for w in self.webapps))
            for webapp in self.webapps:
                self.deploy_webapp(webapp)
        self.run(commands)

    def webapp_dir(self, webapp):
        return '%s/%s/%s' % (self.repos['Backend'], webapp['module'], webapp['project'])

    def deploy_webapp(self, webapp):
        copyfile(
            '%s/build/libs/%s' % (self.webapp_dir(webapp), webapp['war']),
            '%s/%s' % (self.tomcat_webapps, webapp['war'])
        )

    def deps(self, commands):
        # subprocess.Popen(['gradle', 'dependencyCheckAnalyze'], cwd=self.repos['Backend']).wait()

        for webapp in self.webapps:
            webapp_dir = self.webapp_dir(webapp)
            reports_dir = '%s/build/reports' % webapp_dir
            if not os.path.isdir(reports_dir):
                os.mkdir(reports_dir)
            self.shell(['gradle', 'dependencies', '>', '%s/dependency-tree.txt' % reports_dir], cwd=webapp_dir).wait()

        print('\nDEPENDENCY INFORMATION (Ctrl-click links to open)\n')

        for webapp in self.webapps:
            webapp_dir = self.webapp_dir(webapp)
            print('%s dependency tree:' % webapp['name'])
            print('  file:///%s/build/reports/dependency-tree.txt\n' % webapp_dir)
            # print('%s vulnerability scan:' % webapp['name'])
            # print('  file:///%s/build/reports/dependency-check-report.html\n' % webapp_dir)

        self.run(commands)
