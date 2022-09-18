#!/usr/bin/env python3

import argparse
import contextlib
import io
import itertools
import re
import sys
from pathlib import Path
from typing import (
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    TYPE_CHECKING,
    TypeVar,
    Union,
)

import parso
from flake8.main.application import (  # type: ignore[import]
    Application as Flake8,
)
from flake8.style_guide import Decision  # type: ignore[import]
from parso.python import tree

if TYPE_CHECKING:
    from typing_extensions import TypeGuard


FIXER_REGEX = re.compile(r'^fix_([A-Z]{1,3}\d{3})$')

FLAKE8_FORMAT = '%(path)s:%(row)d:%(col)d:%(code)s:%(text)s'


class ErrorDetail(NamedTuple):
    line: int
    col: int
    code: str
    message: str

    def render(self, filename: Path) -> str:
        return f'{filename}:{self.line}:{self.col}: {self.code} {self.message}'


class CodeLine(NamedTuple):
    text: str
    line: int
    col: int


Position = Tuple[int, int]
Span = Tuple[Position, Position]

# TODO: currently we return the new string, we should move to instead returning
# a description of the edit.
LineFixer = Callable[[CodeLine], str]
TLineFixer = TypeVar('TLineFixer', bound=LineFixer)

FileFixer = Callable[[Sequence[ErrorDetail], str], str]
TFileFixer = TypeVar('TFileFixer', bound=FileFixer)

LINE_FIXERS: Dict[str, LineFixer] = {}
FILE_FIXERS: Dict[str, FileFixer] = {}


def merge_overlapping_spans(spans: Sequence[Span]) -> List[Span]:
    if not spans:
        return []

    spans = sorted(spans)

    output_spans = [spans[0]]

    for span in spans[1:]:
        last_start, last_end = output_spans[-1]
        start, end = span

        if start <= last_end:
            output_spans[-1] = last_start, max(last_end, end)
        else:
            output_spans.append(span)

    return output_spans


def insert_character_at(text: str, col: int, char: str) -> str:
    return text[:col] + char + text[col:]


def remove_character_at(text: str, col: int, char: str) -> str:
    # to 0-index
    col -= 1
    assert text[col] == char, f"{text[col]} != {char}"
    return text[:col] + text[col + 1:]


def line_fixer(fn: TLineFixer) -> TLineFixer:
    match = FIXER_REGEX.match(fn.__name__)
    if match is None:
        raise ValueError(
            "LineFixer has invalid name, should be of the form 'fix_X123' but was "
            "{!r}".format(fn.__name__),
        )
    LINE_FIXERS[match.group(1)] = fn
    return fn


def file_fixer(fn: TFileFixer) -> TFileFixer:
    match = FIXER_REGEX.match(fn.__name__)
    if match is None:
        raise ValueError(
            "LineFixer has invalid name, should be of the form 'fix_X123' but was "
            "{!r}".format(fn.__name__),
        )
    FILE_FIXERS[match.group(1)] = fn
    return fn


@line_fixer  # Missing trailing comma
def fix_C812(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@line_fixer  # Missing trailing comma
def fix_C813(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@line_fixer  # Missing trailing comma
def fix_C814(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@line_fixer  # Missing trailing comma
def fix_C815(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@line_fixer  # Missing trailing comma
def fix_C816(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@line_fixer  # Trailing comma prohibited
def fix_C819(code_line: CodeLine) -> str:
    # flake8-commas seems to give the wrong column position, so -1
    return remove_character_at(code_line.text, code_line.col - 1, ',')


@file_fixer
def fix_F401(messages: Sequence[ErrorDetail], content: str) -> str:
    module = parso.parse(content).get_root_node()

    def get_start_pos(node_or_leaf: parso.tree.NodeOrLeaf) -> Position:
        leaf = node_or_leaf.get_first_leaf()
        if leaf.prefix.isspace():
            return leaf.get_start_pos_of_prefix()  # type: ignore[no-any-return]
        return leaf.start_pos  # type: ignore[no-any-return]

    def find_path(
        node: Union[tree.ImportFrom, tree.ImportName],
        import_name: List[str],
        import_as_name: Optional[str],
    ) -> List[tree.Name]:
        for path, as_name in zip(node.get_paths(), node.get_defined_names()):
            if import_as_name is None:
                # Not expecting a rename
                if as_name not in path:
                    # But was a rename
                    continue
            else:
                # Expecting a rename
                if as_name in path:
                    # But wasn't a rename
                    continue

            if all(
                name_str == name_node.get_code(include_prefix=False)
                for name_node, name_str in zip(path, import_name)
            ):
                return path  # type: ignore[no-any-return]

        raise ValueError("Failed to find matching path for {}".format(import_name))

    def on_same_line(a: parso.tree.NodeOrLeaf, b: parso.tree.NodeOrLeaf) -> bool:
        return a.start_pos[0] == b.start_pos[0]

    message_regex = re.compile(r"^'([\w\.]+)(\s+as\s+([\w\.]+))?'")

    def get_part_to_remove(
        detail: ErrorDetail,
        node: Union[tree.ImportFrom, tree.ImportName],
    ) -> Tuple[tree.Name, str]:
        match = message_regex.search(detail.message)
        if match is None:
            raise ValueError("Unable to extract import name from message {!r}".format(
                detail.message,
            ))

        import_name = match.group(1).split('.')
        import_as_name = match.group(3)

        if import_name[:node.level] != [''] * node.level:
            raise ValueError("Source level is shallower than message")

        if import_name[node.level] == ['']:
            raise ValueError("Source level is deeper than message")

        import_name = import_name[node.level:]

        found_path = find_path(node, import_name, import_as_name)
        return found_path[-1], import_as_name

    def get_node_to_remove(
        name: tree.Name,
        import_as_name: Optional[str],
        node: Union[tree.ImportFrom, tree.ImportName],
    ) -> Union[parso.tree.BaseNode, parso.tree.Leaf]:
        assert name.parent is not None  # placate mypy
        if name.parent.parent == node:
            # We're removing something like `bar as spam` from
            #   from foo import bar as spam, quox
            assert not import_as_name, "Expected renamed import, but didn't find it"
            return name

        # We're removing something like `quox` from
        #   from foo import bar as spam, quox
        assert import_as_name, "Did not expect renamed import, but found one"
        return name.parent

    def is_operator(node: parso.tree.NodeOrLeaf, char: str) -> 'TypeGuard[tree.Operator]':
        return isinstance(node, tree.Operator) and node == char

    def operators_to_remove(
        elements: Iterable[parso.tree.NodeOrLeaf],
    ) -> Iterator[tree.Operator]:
        last_was_operator = True
        for element in elements:
            if not is_operator(element, ','):
                last_was_operator = False
                continue

            if last_was_operator:
                yield element

            last_was_operator = True

    def get_parts_to_remove(
        line_messages: Sequence[ErrorDetail],
        node: Union[tree.ImportFrom, tree.ImportName],
    ) -> List[Span]:
        nodes_to_remove = set(
            get_node_to_remove(
                *get_part_to_remove(message, node),
                node,
            )
            for message in line_messages
        )

        parent, = set(x.parent for x in nodes_to_remove)
        assert parent is not None  # placate mypy
        remaining_siblings = [x for x in parent.children if x not in nodes_to_remove]

        nodes_to_remove.update(operators_to_remove(remaining_siblings))

        last_remaining_sibling, = itertools.islice(
            (x for x in reversed(remaining_siblings) if x not in nodes_to_remove),
            1,
        )

        if (
            is_operator(last_remaining_sibling, ',')
            and not is_operator(node.children[-1], ')')
        ):
            nodes_to_remove.add(last_remaining_sibling)

        return [
            (get_start_pos(x), x.end_pos)
            for x in nodes_to_remove
        ]

    spans_to_remove: List[Span] = []

    for lineno, grouped in itertools.groupby(messages, lambda x: x.line):
        line_messages = list(grouped)

        col = min(x.col for x in line_messages)
        node = module.get_leaf_for_position((lineno, col)).parent

        if len(node.get_paths()) == len(line_messages):
            start_pos = get_start_pos(node)
            end_pos = node.end_pos
            spans_to_remove.append((start_pos, end_pos))
            continue

        spans_to_remove += get_parts_to_remove(line_messages, node)

    spans_to_remove = merge_overlapping_spans(spans_to_remove)

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

        if not interim:
            # We're removing a line. If the line after is also empty, then we
            # also want to remove those lines to avoid creating empty lines at
            # the start of the file. This is a specific targetted fix rather
            # than a general attempt at formatting imports (we leave that to
            # e.g: `isort`).
            if after and after[0].isspace():
                after.pop(0)

        lines = before + interim + after

    return ''.join(lines)


@file_fixer
def fix_LBL001(messages: Sequence[ErrorDetail], content: str) -> str:
    return content.lstrip('\n')


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
    # Flake8 v4 assumes stdout is a buffered output and sometimes writes
    # directly to the buffer.
    buffer = io.BytesIO()
    with contextlib.redirect_stdout(io.TextIOWrapper(buffer)) as wrapper:
        flake8 = Flake8()
        flake8.initialize(args + ['--format', FLAKE8_FORMAT])

        # Only run for the checks we can do anything about:
        decider = flake8.guide.decider
        flake8.options.select = [
            code
            for code in LINE_FIXERS.keys()
            if decider.decision_for(code) == Decision.Selected
        ]
        flake8.run_checks()
        flake8.report()

        # Flush the wrapper to the buffer. This is needed for Flake8 v3 which
        # writes to the wrapper not the buffer.
        wrapper.flush()
        # Note: the wrapper will close our buffer when it gets closed, so need to
        # get the value while it's still alive.
        output = buffer.getvalue().decode()

    return parse_flake8_output(output)


def process_errors(messages: List[ErrorDetail], content: str) -> str:
    lines = content.splitlines()
    modified = False

    for message in sorted(messages, reverse=True):
        line_fixer_fn = LINE_FIXERS.get(message.code)
        if not line_fixer_fn:
            continue

        # Convert to 0-based
        lineno = message.line - 1

        new_line = line_fixer_fn(CodeLine(lines[lineno], lineno, message.col))
        if new_line == lines[lineno]:
            continue

        lines[lineno] = new_line
        modified = True

    if modified:
        content = ''.join(x.rstrip() + '\n' for x in lines)

    for code, fixer_fn in FILE_FIXERS.items():
        relevant_messages = [x for x in messages if x.code == code]
        if relevant_messages:
            content = fixer_fn(relevant_messages, content)

    return content


def run(args: argparse.Namespace) -> None:
    all_error_details = run_flake8(args.flake8_args)

    for filepath, error_details in all_error_details.items():
        if error_details[0].code == 'E999':
            print(error_details[0].render(filepath))
            continue

        with filepath.open(mode='r+') as f:
            content = f.read()
            new_content = process_errors(error_details, content)

            if new_content != content:
                print("Fixing {}".format(filepath))
                f.seek(0)
                f.write(new_content)
                f.truncate()


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('flake8_args', metavar='FLAKE8_ARG', nargs='*')
    return parser.parse_args(argv)


def main(argv: List[str] = sys.argv[1:]) -> None:
    return run(parse_args(argv))


if __name__ == '__main__':
    main()
