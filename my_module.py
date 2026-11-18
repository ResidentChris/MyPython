"""The contract between my.py and the command modules (my_git, my_gradle, ...).

`MyModule` is the protocol my.py depends on. `MyAbstractModule` is an
optional base class that implements it, enforces its required class
members, and provides shared behaviour such as help handling. A module can
implement `MyModule` directly instead of extending `MyAbstractModule`.
"""

from abc import ABC, abstractmethod
from typing import ClassVar, Protocol

HELP_COMMANDS = ('help', '-h', '--help')


class MyModule(Protocol):
    """What my.py needs from a command module.

    my.py reads `command` and `descriptions` from the class before
    constructing it, so both are class-level members.
    """

    # The name used on the command line, e.g. 'gradle' for `my gradle ...`.
    command: ClassVar[str]

    # Help text for each sub-command, e.g. {'clean': 'Run ./gradlew clean'}.
    descriptions: ClassVar[dict[str, str]]

    def run(self, commands: list[str]) -> None:
        """Consume the leading commands this module handles.

        Anything this module doesn't handle is left at the front of
        `commands` for my.py.
        """
        ...


class MyAbstractModule(MyModule, ABC):
    """Optional base class for command modules.

    Subclasses must define `command` (a non-empty string) and
    `descriptions` (a dict) as class attributes; this is checked when the
    subclass is defined, so a missing member fails on import. They must
    also implement `run`.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        command = getattr(cls, 'command', None)
        if not isinstance(command, str) or not command:
            raise TypeError(
                "%s must define a non-empty 'command' class attribute" % cls.__name__)

        descriptions = getattr(cls, 'descriptions', None)
        if not isinstance(descriptions, dict):
            raise TypeError(
                "%s must define a 'descriptions' class attribute (a dict)" % cls.__name__)

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
