#!/usr/bin/env python

import argparse
import ast
import functools
import itertools
import re
import subprocess
import token
from pathlib import Path
from typing import (
    Callable,
    Dict,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

import asttokens.util  # type: ignore[import]
from asttokens import ASTTokens

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


def _first_token(node: ast.AST) -> asttokens.util.Token:
    return node.first_token  # type: ignore[attr-defined]


def _last_token(node: ast.AST) -> asttokens.util.Token:
    return node.last_token  # type: ignore[attr-defined]


@functools.total_ordering
class Position:
    """
    A position within a document, compatible with Python AST positions.

    Line numbers are one-based, columns are zero-based.
    """

    @classmethod
    def from_node_start(cls, node: ast.AST) -> 'Position':
        return cls(*_first_token(node).start)

    @classmethod
    def from_node_end(cls, node: ast.AST) -> 'Position':
        return cls(*_last_token(node).start)

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


class NodeFinder(ast.NodeVisitor):
    def __init__(
        self,
        position: Position,
        target_node_types: Tuple[Type[ast.AST], ...],
    ) -> None:
        self.target_position = position
        self.target_node_types = target_node_types

        self.node_stack = []  # type: List[ast.AST]

        self.found = False

    @property
    def found_node(self) -> ast.AST:
        if not self.found:
            raise ValueError("No node found!")

        try:
            return next(
                node
                for node in reversed(self.node_stack)
                if isinstance(node, self.target_node_types)
            )
        except StopIteration:
            raise ValueError(
                "No supported nodes found (stack: {})".format(
                    " > ".join(type(x).__name__ for x in self.node_stack),
                ),
            ) from None

    def generic_visit(self, node: ast.AST) -> None:
        if self.found:
            return

        if not hasattr(node, 'lineno'):
            super().generic_visit(node)
            return

        start = Position.from_node_start(node)
        end = Position.from_node_end(node)

        if end < self.target_position:
            # we're clear before the target
            return

        if start > self.target_position:
            # we're clear after the target
            return

        # we're on the path to finding the desired node
        self.node_stack.append(node)

        super().generic_visit(node)

        self.found = True


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
    asttokens = ASTTokens(content, parse=True)

    message_regex = re.compile(r"^'([\w\.]+)(\s+as\s+([\w\.]+))?'")

    spans_to_remove = []

    for message in messages:
        match = message_regex.search(message.message)
        if match is None:
            raise ValueError("Unable to extract import name from message {!r}".format(
                message.message,
            ))

        import_name = match.group(1)
        import_as_name = match.group(3)

        position = Position(message.line, message.col)
        finder = NodeFinder(position, (ast.Import, ast.ImportFrom))
        finder.visit(asttokens.tree)
        node = finder.found_node

        assert isinstance(node, (ast.Import, ast.ImportFrom))

        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert import_name.startswith(node.module)
            import_name = import_name[len(node.module) + 1:]

        import_matches = [
            name
            for name in node.names
            if import_name == name.name and import_as_name == name.asname
        ]

        if not import_matches:
            raise ValueError("Failed to find import to remove")

        if len(node.names) == 1:
            start_pos = _first_token(node).startpos
            end_pos = _last_token(node).endpos
        else:
            if import_as_name:
                raise ValueError("Removing renamed imports from a list is not supported")

            # Do the locating ourselves. ASTtokens doesn't add loction
            # information for imports; see https://github.com/gristlabs/asttokens/issues/27.
            node_to_remove, = import_matches

            name_token = asttokens.find_token(
                _first_token(node),
                token.NAME,
                node_to_remove.name,
            )
            start_pos = name_token.startpos

            comma_or_paren = asttokens.next_token(name_token)
            if comma_or_paren.string == ',':
                end_pos = comma_or_paren.endpos
            else:
                end_pos = name_token.endpos

        spans_to_remove.append((start_pos, end_pos))

    # TODO: validate no overlaps
    for start_pos, end_pos in sorted(spans_to_remove, reverse=True):
        content = content[:start_pos].rstrip() + content[end_pos:]

    return content


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
        error_details[Path(filepath)] = sorted(
            ErrorDetail(line=int(line), col=int(col), code=code, message=message)
            for (_, line, col, code, message) in messages
        )

    return error_details


def run_flake8(
    args: List[str],
    _input: Optional[bytes] = None,
) -> Dict[Path, List[ErrorDetail]]:
    flake8_result = subprocess.run(
        ['flake8'] + args + ['--format', FLAKE8_FORMAT],
        input=_input,
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
