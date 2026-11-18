"""The contract between my.py and the command modules (my_git, my_gradle, ...).

`MyModule` is the protocol my.py depends on. `MyAbstractModule` is an
optional base class that implements it and provides shared behaviour such
as help handling. A module can implement `MyModule` directly instead of
extending `MyAbstractModule`.

Conformance is checked by the tests in test_my_module.py, not at import.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Iterable, Protocol, runtime_checkable

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
    constructor, which the shared `help` uses.
    """

    descriptions: dict[str, str]

    @classmethod
    @abstractmethod
    def command(cls) -> str:
        ...

    @abstractmethod
    def run(self, commands: list[str]) -> None:
        ...

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
