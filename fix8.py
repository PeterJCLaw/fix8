#!/usr/bin/env python

import argparse
import functools
import io
import itertools
import re
import sys
from pathlib import Path
from typing import (
    Callable,
    Dict,
    List,
    NamedTuple,
    Sequence,
    Tuple,
    TypeVar,
)

import parso  # type: ignore[import]
from flake8.main.application import (  # type: ignore[import]
    Application as Flake8,
)
from parso.python import tree  # type: ignore[import]

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


@functools.total_ordering
class Position:
    """
    A position within a document, compatible with Python AST positions.

    Line numbers are one-based, columns are zero-based.
    """

    def __init__(self, line: int, col: int) -> None:
        self.line = line
        self.col = col

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented

        return self.line == other.line and self.col == other.col

    def __lt__(self, other: 'Position') -> bool:
        if not isinstance(other, Position):
            return NotImplemented  # type: ignore  # unreachable

        if self.line < other.line:
            return True

        if self.line > other.line:
            return False

        return self.col < other.col

    def __repr__(self) -> str:
        return 'Position(line={}, col={})'.format(self.line, self.col)


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


def fix_F401(messages: Sequence[ErrorDetail], content: str) -> str:
    module = parso.parse(content).get_root_node()

    def get_start_pos(leaf: parso.tree.NodeOrLeaf) -> Tuple[int, int]:
        if isinstance(leaf, parso.tree.Leaf) and leaf.prefix.isspace():
            return leaf.get_start_pos_of_prefix()  # type: ignore[no-any-return]
        return leaf.start_pos  # type: ignore[no-any-return]

    def find_path(node: tree.Import, import_name: List[str]) -> tree.Name:
        for path in node.get_paths():
            if all(
                name_str == name_node.get_code(include_prefix=False)
                for name_node, name_str in zip(path, import_name)
            ):
                return path

        raise ValueError("Failed to find matching path for {}".format(import_name))

    def on_same_line(a: parso.tree.BaseNode, b: parso.tree.BaseNode) -> bool:
        return a.start_pos[0] == b.start_pos[0]  # type: ignore[no-any-return]

    message_regex = re.compile(r"^'([\w\.]+)(\s+as\s+([\w\.]+))?'")

    spans_to_remove = []

    for message in messages:
        match = message_regex.search(message.message)
        if match is None:
            raise ValueError("Unable to extract import name from message {!r}".format(
                message.message,
            ))

        import_name = match.group(1).split('.')
        import_as_name = match.group(3)

        node = module.get_leaf_for_position((message.line, message.col)).parent

        if import_name[:node.level] != [''] * node.level:
            raise ValueError("Source level is shallower than message")

        if import_name[node.level] == ['']:
            raise ValueError("Source level is deeper than message")

        import_name = import_name[node.level:]

        found_path = find_path(node, import_name)

        if len(node.get_paths()) == 1:
            start_pos = get_start_pos(node)
            end_pos = node.end_pos
        else:
            last_part = found_path[-1]
            if last_part.parent.parent == node:
                # TODO: I think there's a case where this can happen (`import foo, foo as bar`)
                assert not import_as_name, "Expected renamed import, but didn't find it"
                node_to_remove = last_part
            else:
                # TODO: I think there's a case where this can happen (`import foo as bar, foo`)
                assert import_as_name, "Did not expect renamed import, but found one"
                node_to_remove = last_part.parent

            start_pos = get_start_pos(node_to_remove)

            next_leaf = node_to_remove.get_next_leaf()
            if next_leaf.type == 'operator':
                end_pos = next_leaf.end_pos

                prev_leaf = last_part.get_previous_leaf()
                if on_same_line(prev_leaf, last_part) and prev_leaf.type == 'operator':
                    start_pos = prev_leaf.end_pos

            else:
                end_pos = node_to_remove.end_pos

                prev_leaf = last_part.get_previous_leaf()
                if on_same_line(prev_leaf, last_part) and prev_leaf.type == 'operator':
                    start_pos = get_start_pos(prev_leaf)

        spans_to_remove.append((start_pos, end_pos))

    # TODO: validate no overlaps
    lines = content.splitlines(True)
    for (start_line, start_col), (end_line, end_col) in sorted(
        spans_to_remove,
        reverse=True,
    ):
        # Note: lines start from 1 but need to use 0-indexed list lookup.
        # However, we _also_ want to *include* the end line in our edit block,
        # so we'd need to add one back and thus make no change to the end line
        start_line -= 1

        before, interim, after = \
            lines[:start_line], lines[start_line:end_line], lines[end_line:]

        line = interim[0][:start_col] + interim[-1][end_col:]

        interim = [] if line.isspace() else [line]

        lines = before + interim + after

    return ''.join(lines)


def parse_flake8_output(flake8_output: str) -> Dict[Path, List[ErrorDetail]]:
    """
    Parse output from Flake8 formatted using FLAKE8_FORMAT into a useful form.
    """
    lines = [
        x.split(':', maxsplit=4)
        for x in sorted(flake8_output.splitlines())
    ]

    grouped_lines = itertools.groupby(lines, lambda x: x[0])

    error_details = {}
    for filepath, messages in grouped_lines:
        error_details[Path(filepath)] = sorted(
            ErrorDetail(line=int(line), col=int(col), code=code, message=message)
            for (_, line, col, code, message) in messages
        )

    return error_details


def run_flake8(args: List[str]) -> Dict[Path, List[ErrorDetail]]:
    output = io.StringIO()
    stdout = sys.stdout
    sys.stdout = output

    Flake8().run(args + ['--format', FLAKE8_FORMAT])

    sys.stdout = stdout

    return parse_flake8_output(output.getvalue())


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

    # TODO: generalise support for other whole-file fixes
    f401_messages = [x for x in messages if x.code == 'F401']
    if f401_messages:
        content = fix_F401(f401_messages, content)

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
    parser.add_argument('flake8_args', metavar='FLAKE8_ARG', nargs='*')
    return parser.parse_args()


if __name__ == '__main__':
    main(parse_args())
