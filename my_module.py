"""The contract between my.py and the command modules (my_git, my_gradle, ...).

`MyModule` is the protocol my.py depends on. `MyAbstractModule` is an
optional base class that implements it and provides shared behaviour such
as help handling. A module can implement `MyModule` directly instead of
extending `MyAbstractModule`.

Conformance is checked by the tests in test_my_module.py, not at import.
"""

import inspect
import shlex
import subprocess
from abc import ABC, abstractmethod
from typing import Iterable, Protocol, runtime_checkable

from my_colours import Colour

HELP_COMMANDS = ('help', '-h', '--help')


@runtime_checkable
class MyModule(Protocol):
    """What my.py needs from a command module.

    Every member is a method, so `issubclass(cls, MyModule)` can be used to
    discover modules. `command` is a classmethod because my.py needs it
    before constructing the module. Every module must support `help`, so
    that `my <command> help` always works.
    """

    @classmethod
    def command(cls) -> str:
        """The name used on the command line, e.g. 'gradle' for `my gradle ...`."""
        ...

    def run(self, commands: list[str]) -> None:
        """Consume the leading commands this module handles.

        Anything this module doesn't handle is left at the front of
        `commands` for my.py. `help`, `-h` and `--help` must be handled by
        calling `help`.
        """
        ...

    def help(self, commands: list[str]) -> None:
        """Print help for this module's sub-commands.

        May consume a sub-command name from the front of `commands` to show
        help for just that sub-command.
        """
        ...


class MyAbstractModule(MyModule, ABC):
    """Optional base class for command modules.

    Subclasses must implement `command` and `run`, and set
    `self.descriptions` (sub-command name -> help text) in their
    constructor, which the shared `help` uses. They run external commands
    through `shell`.
    """

    descriptions: dict[str, str]

    # What `shell` uses to run commands. Replace it (e.g. on an instance in
    # tests) to change how every command in the module is run.
    shell_implementation = subprocess.Popen

    @classmethod
    @abstractmethod
    def command(cls) -> str:
        ...

    @abstractmethod
    def run(self, commands: list[str]) -> None:
        ...

    def shell(self, *args, **kwargs) -> subprocess.Popen:
        """Run an external command. Takes the same arguments as subprocess.Popen.

        The command is printed before it runs.
        """
        command = args[0] if args else kwargs.get('args')
        if command is not None:
            text = command if isinstance(command, str) else shlex.join(str(part) for part in command)
            print('%s$ %s%s' % (Colour.BLUE.value, text, Colour.CLEAR.value))
        return self.shell_implementation(*args, **kwargs)

    @staticmethod
    def is_help(command: str) -> bool:
        return command in HELP_COMMANDS

    def help(self, commands: list[str]) -> None:
        """Print help for one sub-command, or list them all.

        `help <sub-command>` consumes the sub-command and continues with
        any remaining commands. Plain `help` lists every sub-command.
        """
        if len(commands) >= 1 and commands[0] in self.descriptions:
            command = commands.pop(0)
            print('    %-10s %s' % (command, self.descriptions[command]))
            self.run(commands)
        else:
            print('Possible commands are:')
            for command, description in self.descriptions.items():
                print('    %-10s %s' % (command, description))


def find_modules(classes: Iterable[type]) -> list[type[MyModule]]:
    """The classes that are usable command modules.

    Excludes `MyModule` itself, abstract classes (such as
    `MyAbstractModule`, or a subclass that is missing a required method),
    and anything that doesn't implement `MyModule`.
    """
    return [
        cls for cls in classes
        if cls is not MyModule
        and issubclass(cls, MyModule)
        and not inspect.isabstract(cls)
    ]
