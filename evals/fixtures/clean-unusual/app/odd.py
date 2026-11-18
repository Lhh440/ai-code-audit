import sys
from itertools import chain


def flat(*groups):
    return list(chain.from_iterable(groups))


def loudly(message, *, prefix="!"):
    print(prefix, message, file=sys.stderr)
    return message.upper()


def swap(pairs):
    return {value: key for key, value in pairs}
