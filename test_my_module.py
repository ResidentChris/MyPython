import inspect
import unittest
from unittest.mock import patch

import my
from my_colours import Colour
from my_module import MyAbstractModule, MyModule, find_modules


class ExampleModule(MyAbstractModule):
    @classmethod
    def command(cls):
        return 'example'

    def __init__(self):
        self.descriptions = {'first': 'The first sub-command', 'second': 'The second sub-command'}
        self.ran = []

    def run(self, commands):
        while commands and commands[0] in self.descriptions:
            self.ran.append(commands.pop(0))
        if commands and self.is_help(commands[0]):
            commands.pop(0)
            self.help(commands)


class StandaloneModule:
    """Implements MyModule without extending MyAbstractModule."""

    @classmethod
    def command(cls):
        return 'standalone'

    def run(self, commands):
        if commands and commands[0] == 'help':
            self.help(commands[1:])

    def help(self, commands):
        print('Standalone has no sub-commands')


class NoCommand(MyAbstractModule):
    def run(self, commands):
        pass


class NoHelp:
    """Has command and run, but no help, so isn't a MyModule."""

    @classmethod
    def command(cls):
        return 'nohelp'

    def run(self, commands):
        pass


class MyAbstractModuleTests(unittest.TestCase):
    def test_missing_command_makes_the_class_abstract(self):
        self.assertTrue(inspect.isabstract(NoCommand))
        with self.assertRaises(TypeError):
            NoCommand()

    def test_missing_run_makes_the_class_abstract(self):
        class NoRun(MyAbstractModule):
            @classmethod
            def command(cls):
                return 'norun'

        self.assertTrue(inspect.isabstract(NoRun))
        with self.assertRaises(TypeError):
            NoRun()

    def test_complete_module_can_be_instantiated(self):
        module = ExampleModule()
        self.assertEqual(module.command(), 'example')
        self.assertIsInstance(module, MyAbstractModule)


class FindModulesTests(unittest.TestCase):
    def test_finds_subclasses_and_standalone_implementations(self):
        self.assertEqual(find_modules([ExampleModule, StandaloneModule]),
                         [ExampleModule, StandaloneModule])

    def test_command_is_readable_without_constructing_the_class(self):
        self.assertEqual([m.command() for m in find_modules([ExampleModule, StandaloneModule])],
                         ['example', 'standalone'])

    def test_excludes_the_protocol_and_abstract_classes(self):
        self.assertEqual(find_modules([MyModule, MyAbstractModule, NoCommand]), [])

    def test_excludes_classes_that_do_not_implement_the_protocol(self):
        self.assertEqual(find_modules([Colour, NoHelp, dict]), [])


class MyAbstractModuleHelpTests(unittest.TestCase):
    def test_help_flags_are_recognised(self):
        for flag in ['help', '-h', '--help']:
            with self.subTest(flag=flag):
                self.assertTrue(MyAbstractModule.is_help(flag))
        self.assertFalse(MyAbstractModule.is_help('first'))

    def test_help_lists_all_commands_and_consumes_nothing_else(self):
        module = ExampleModule()
        commands = ['unknown']
        with patch('builtins.print'):
            module.help(commands)
        self.assertEqual(commands, ['unknown'])
        self.assertEqual(module.ran, [])

    def test_help_for_a_command_consumes_it_without_running_it(self):
        module = ExampleModule()
        commands = ['first']
        with patch('builtins.print'):
            module.help(commands)
        self.assertEqual(commands, [])
        self.assertEqual(module.ran, [])

    def test_help_for_a_command_continues_with_remaining_commands(self):
        module = ExampleModule()
        commands = ['first', 'second']
        with patch('builtins.print'):
            module.help(commands)
        self.assertEqual(commands, [])
        self.assertEqual(module.ran, ['second'])


# Fake configuration, enough to construct every command module.
ARGUMENTS = {
    'git': {'repos': {'FrontEnd': '/fake/frontend'}},
    'tomcat': {'tomcat_home': '/fake/tomcat'},
    'gradle': {'webapps': []},
    'harness': {'folder': '/fake/harness', 'url': 'http://localhost'},
    'npm': {'wsl_user': 'tester', 'environment': {}},
    'qmk': {'folder': '/fake/qmk', 'keyboard': 'kb', 'keymap': 'km'},
    'xc': {'folder': '/fake/xc', 'workspace': 'App.xcworkspace', 'scheme': 'App'},
}


def classes_imported_into_my():
    return [cls for _, cls in inspect.getmembers(my, inspect.isclass)]


class CommandModuleComplianceTests(unittest.TestCase):
    """Checks every command module imported into my.py, so new modules are covered automatically."""

    def test_the_expected_commands_are_discovered(self):
        self.assertEqual(sorted(my.command_modules()),
                         ['git', 'gradle', 'harness', 'npm', 'qmk', 'xc'])

    def test_no_imported_module_is_left_abstract(self):
        # A MyAbstractModule subclass missing a method would be silently
        # skipped by discovery, so fail here instead.
        for cls in classes_imported_into_my():
            if issubclass(cls, MyAbstractModule):
                with self.subTest(module=cls.__name__):
                    self.assertFalse(inspect.isabstract(cls),
                                     '%s is missing a required method' % cls.__name__)

    def test_commands_are_non_empty_and_unique(self):
        commands = [cls.command() for cls in find_modules(classes_imported_into_my())]
        for command in commands:
            with self.subTest(command=command):
                self.assertIsInstance(command, str)
                self.assertTrue(command)
                self.assertEqual(command, command.lower())
        self.assertEqual(len(commands), len(set(commands)), 'Duplicate commands: %s' % commands)

    def test_help_is_consumed_and_prints_something(self):
        for command, cls in my.command_modules().items():
            for flag in ['help', '-h', '--help']:
                with self.subTest(command=command, flag=flag):
                    with patch('builtins.print') as printed:
                        module = cls([], ARGUMENTS, '/fake/repo', '/fake/logs')
                        printed.reset_mock()
                        commands = [flag]
                        module.run(commands)
                    self.assertEqual(commands, [])
                    self.assertTrue(printed.called)

    def test_help_leaves_unknown_commands_for_my(self):
        for command, cls in my.command_modules().items():
            with self.subTest(command=command):
                with patch('builtins.print'):
                    module = cls([], ARGUMENTS, '/fake/repo', '/fake/logs')
                    commands = ['help', 'not-a-sub-command']
                    module.run(commands)
                self.assertEqual(commands, ['not-a-sub-command'])


if __name__ == '__main__':
    unittest.main()
