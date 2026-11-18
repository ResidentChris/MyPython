#!/usr/bin/env python

import os
import sys
from shutil import copyfile
from time import time
from my_colours import Colour
from my_module import MyAbstractModule


class MyGradle(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'gradle'

    def __init__(self, commands, arguments, repositories, logs, prompt=input):
        self.repos = arguments['git']['repos']
        self.logs = logs
        self.tomcat_webapps = '%s/Webapps' % arguments['tomcat']['tomcat_home']
        self.webapps = arguments['gradle']['webapps']
        self.prompt = prompt
        self.descriptions = {
            'clean': 'Run ./gradlew clean',
            'format': 'Run ./gradlew format',
            'test': 'Run ./gradlew test, stopping if the tests fail',
            'install': 'Run ./gradlew build (add "quickly" to skip tests)',
            'build': 'Alias for install',
            'assemble': 'Run ./gradlew assemble, skipping tests',
            'publish': 'Run ./gradlew publishToMavenLocal, stopping if it fails',
            'deploy': 'Copy the WAR for the webapp in the current directory into Tomcat webapps',
            'deps': 'Write each webapp\'s dependency tree to build/reports',
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

            elif command == "install" or command == 'build':
                self.install(commands)

            elif command == 'assemble':
                self.install(commands, True)

            elif command == "publish":
                self.publish(commands)

            elif command == "deploy":
                self.deploy(commands)

            elif command == "deps":
                self.deps(commands)

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

        install_commands = [self.gradlew(os.getcwd()), 'assemble' if skip_tests else 'build']

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

    def deploy(self, commands):
        cwd = os.getcwd()
        for webapp in self.webapps:
            if cwd.endswith(webapp['module']):
                print('Deploying %s only.' % webapp['abbreviation'])
                self.deploy_webapp(webapp)
                break
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
            self.shell([self.gradlew(webapp_dir), 'dependencies', '>', '%s/dependency-tree.txt' % reports_dir], cwd=webapp_dir).wait()

        print('\nDEPENDENCY INFORMATION (Ctrl-click links to open)\n')

        for webapp in self.webapps:
            webapp_dir = self.webapp_dir(webapp)
            print('%s dependency tree:' % webapp['name'])
            print('  file:///%s/build/reports/dependency-tree.txt\n' % webapp_dir)
            # print('%s vulnerability scan:' % webapp['name'])
            # print('  file:///%s/build/reports/dependency-check-report.html\n' % webapp_dir)

        self.run(commands)
