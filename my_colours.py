from enum import Enum
from functools import reduce

class Colour(Enum):
    RED = '\033[91m'
    GREEN = '\033[92m'
    BLUE = '\033[1;94m'
    YELLOW = '\033[1;33m'
    CLEAR = '\033[00m'

class Options:
    def __init__(self, *args):
        self._options = args

    def colour_option(self, option):
        return ''.join([
            Colour.CLEAR.value,
            '(',
            option[1].value,
            option[0][0],
            Colour.CLEAR.value,
            ')',
            option[1].value,
            option[0][1:],
            Colour.CLEAR.value
        ])

    def __str__(self):
        return ', '.join([self.colour_option(o) for o in self._options])
