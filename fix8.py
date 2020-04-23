#!/usr/bin/env python

import itertools
import re
import subprocess
import sys
from typing import Callable, Dict, NamedTuple, TypeVar

FIXER_REGEX = re.compile(r'^fix_([A-Z]\d{3})$')

CodeLine = NamedTuple('CodeLine', (
    ('text', str),
    ('line', int),
    ('col', int),
))


# TODO: currently we return the new string, we should move to instead returning
# a description of the edit.
Fixer = Callable[[CodeLine], str]
TFixer = TypeVar('TFixer', bound=Fixer)

FIXERS = {}  # type: Dict[str, Fixer]


def insert_character_at(text: str, col: int, char: str) -> str:
    return text[:col] + char + text[col:]


def remove_character_at(text: str, col: int, char: str) -> str:
    assert text[col] == char
    return text[:col] + text[col + 1:]


def ensure_single_space_at(text: str, col: int) -> str:
    while text[col] == ' ':
        text = remove_character_at(text, col, ' ')

    return insert_character_at(text, col, ' ')


def fixer(fn: TFixer) -> TFixer:
    match = FIXER_REGEX.match(fn.__name__)
    if match is None:
        raise ValueError(
            "Fixer has invalid name, should be of the form 'fix_X123' but was "
            "{!r}".format(fn.__name__),
        )
    FIXERS[match.group(1)] = fn
    return fn


@fixer  # Missing trailing comma
def fix_C812(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@fixer  # Multiple spaces after operator
def fix_E222(code_line: CodeLine) -> str:
    return ensure_single_space_at(code_line.text, code_line.col)


@fixer  # Missing whitespace around operator
def fix_E225(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ' ')


@fixer  # inline comment should start with '# '
def fix_E262(code_line: CodeLine) -> str:
    text, _, col = code_line

    # Actually insert at the next column
    col += 1

    return ensure_single_space_at(text, col)


@fixer  # expected 2 blank lines, found 1
def fix_E302(code_line: CodeLine) -> str:
    return "\n" + code_line.text


@fixer  # the backslash is redundant between brackets
def fix_E502(code_line: CodeLine) -> str:
    return remove_character_at(code_line.text, code_line.col, '\\')


flake_output = subprocess.run(
    ['flake8'] + sys.argv[1:],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
).stdout

error_details = [
    x.split(':', maxsplit=3)
    for x in flake_output.decode('utf-8').splitlines()
]

for filepath, positions in itertools.groupby(error_details, lambda x: x[0]):
    with open(filepath, mode='r+') as f:
        lines = f.readlines()

        for _, lineno_str, col_str, message in positions:
            code = message.split()[0]

            fixer_fn = FIXERS.get(code)
            if not fixer_fn:
                continue

            lineno = int(lineno_str) - 1
            col = int(col_str) - 1

            lines[lineno] = fixer_fn(CodeLine(lines[lineno], lineno, col))

        f.seek(0)
        f.write(''.join(x.rstrip() + '\n' for x in lines))
        f.truncate()
