#!/usr/bin/env python

import argparse
import itertools
import re
import subprocess
import sys
from pathlib import Path
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Sequence,
    TypeVar,
)

FIXER_REGEX = re.compile(r'^fix_([A-Z]\d{3})$')

FLAKE8_FORMAT = '%(path)s:%(row)d:%(col)d:%(code)s:%(text)s'

ErrorDetail = NamedTuple('ErrorDetail', (
    ('line', int),
    ('col', int),
    ('code', str),
    ('message', str),
))

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


def parse_flake8_output(flake8_output: bytes) -> Dict[Path, List[ErrorDetail]]:
    """
    Parse output from Flake8 formatted using FLAKE8_FORMAT into a useful form.
    """
    lines = [
        x.split(':', maxsplit=4)
        for x in sorted(flake8_output.decode('utf-8').splitlines())
    ]

    grouped_lines = itertools.groupby(lines, lambda x: x[0])

    error_details = {}
    for filepath, messages in grouped_lines:
        error_details[Path(filepath)] = [
            ErrorDetail(line=int(line), col=int(col), code=code, message=message)
            for (_, line, col, code, message) in messages
        ]

    return error_details


def run_flake8(args: List[str]) -> Dict[Path, List[ErrorDetail]]:
    flake8_result = subprocess.run(
        ['flake8'] + args + ['--format', FLAKE8_FORMAT],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return parse_flake8_output(flake8_result.stdout)


def process_errors(messages: List[ErrorDetail], content: str) -> str:
    lines = content.splitlines()
    modified = False

    for message in messages:
        fixer_fn = FIXERS.get(message.code)
        if not fixer_fn:
            continue

        # Convert to 0-based
        lineno = message.line - 1

        new_line = fixer_fn(CodeLine(lines[lineno], lineno, message.col))
        if new_line == lines[lineno]:
            continue

        lines[lineno] = new_line
        modified = True

    if modified:
        content = ''.join(x.rstrip() + '\n' for x in lines)

    return content


def main(args: argparse.Namespace) -> None:
    all_error_details = run_flake8(args.flake8_args)

    for filepath, error_details in all_error_details.items():
        with filepath.open(mode='r+') as f:
            content = f.read()
            new_content = process_errors(error_details, content)

            if new_content != content:
                f.seek(0)
                f.write(new_content)
                f.truncate()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('flake8_args', metavar='FLAKE8_ARG', nargs='+')
    return parser.parse_args()


if __name__ == '__main__':
    main(parse_args())
