"""Shared test doubles for the injectable shell/prompt seam.

Not a test module itself - imported by the test_my_*.py files so each one
doesn't have to redefine the same fakes.
"""


class FakeProcess:
    """Stands in for a subprocess.Popen instance."""

    def __init__(self, returncode=0, stdout=b''):
        self.returncode = returncode
        self._stdout = stdout

    def wait(self):
        return self.returncode

    def communicate(self):
        return (self._stdout, None)


class FakeShell:
    """Stands in for subprocess.Popen itself.

    Records every call as (args, kwargs) in `.calls`. Returns FakeProcess
    instances from `responses` in order, one per call; once exhausted, the
    last response is reused for any further calls. Defaults to a single
    successful FakeProcess.
    """

    def __init__(self, responses=None):
        self.calls = []
        self._responses = list(responses) if responses else [FakeProcess()]

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


def queued_prompt(*responses):
    """Returns a callable usable as `prompt=`, yielding each response in turn.

    Raises IndexError if asked for more responses than were queued - that's
    a signal the code under test prompted more times than the test expected.
    """
    remaining = list(responses)

    def prompt(message=''):
        return remaining.pop(0)

    return prompt


def queued_select(*indices):
    """Returns a callable usable as `select=`, yielding each queued index in turn.

    Mirrors queued_prompt() for the menu-selection seam - the real
    interactive widget is never exercised under test. Queue `None` to
    simulate the user cancelling the menu.
    """
    remaining = list(indices)

    def select(items):
        return remaining.pop(0)

    return select
