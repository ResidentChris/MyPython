import unittest
from unittest.mock import patch

from my_module import MyAbstractModule, MyModule


class ExampleModule(MyAbstractModule):
    command = 'example'
    descriptions = {'first': 'The first sub-command', 'second': 'The second sub-command'}

    def __init__(self):
        self.ran = []

    def run(self, commands):
        while commands and commands[0] in self.descriptions:
            self.ran.append(commands.pop(0))
        if commands and self.is_help(commands[0]):
            commands.pop(0)
            self.help(commands)


class StandaloneModule:
    """Implements MyModule without extending MyAbstractModule."""
    command = 'standalone'
    descriptions = {}

    def run(self, commands):
        pass


class MyAbstractModuleEnforcementTests(unittest.TestCase):
    def test_missing_command_fails_when_class_is_defined(self):
        with self.assertRaises(TypeError):
            class NoCommand(MyAbstractModule):
                descriptions = {}

                def run(self, commands):
                    pass

    def test_empty_command_fails_when_class_is_defined(self):
        with self.assertRaises(TypeError):
            class EmptyCommand(MyAbstractModule):
                command = ''
                descriptions = {}

                def run(self, commands):
                    pass

    def test_non_string_command_fails_when_class_is_defined(self):
        with self.assertRaises(TypeError):
            class NumericCommand(MyAbstractModule):
                command = 42
                descriptions = {}

                def run(self, commands):
                    pass

    def test_missing_descriptions_fails_when_class_is_defined(self):
        with self.assertRaises(TypeError):
            class NoDescriptions(MyAbstractModule):
                command = 'nodescriptions'

                def run(self, commands):
                    pass

    def test_missing_run_fails_when_instantiated(self):
        class NoRun(MyAbstractModule):
            command = 'norun'
            descriptions = {}

        with self.assertRaises(TypeError):
            NoRun()

    def test_complete_module_can_be_instantiated(self):
        module = ExampleModule()
        self.assertEqual(module.command, 'example')
        self.assertIsInstance(module, MyAbstractModule)


class MyModuleProtocolTests(unittest.TestCase):
    def test_command_is_readable_without_constructing_the_class(self):
        modules: list[type[MyModule]] = [ExampleModule, StandaloneModule]
        self.assertEqual([m.command for m in modules], ['example', 'standalone'])


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


if __name__ == '__main__':
    unittest.main()
