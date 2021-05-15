#!/usr/bin/env python

import argparse
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
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import parso
from flake8.main.application import (  # type: ignore[import]
    Application as Flake8,
)
from flake8.style_guide import Decision  # type: ignore[import]
from parso.python import tree

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

Position = Tuple[int, int]
Span = Tuple[Position, Position]

# TODO: currently we return the new string, we should move to instead returning
# a description of the edit.
Fixer = Callable[[CodeLine], str]
TFixer = TypeVar('TFixer', bound=Fixer)

FIXERS = {}  # type: Dict[str, Fixer]


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


@fixer  # Missing trailing comma
def fix_C813(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@fixer  # Missing trailing comma
def fix_C814(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@fixer  # Missing trailing comma
def fix_C815(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


@fixer  # Missing trailing comma
def fix_C816(code_line: CodeLine) -> str:
    return insert_character_at(code_line.text, code_line.col, ',')


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
        return a.start_pos[0] == b.start_pos[0]  # type: ignore[no-any-return]

    message_regex = re.compile(r"^'([\w\.]+)(\s+as\s+([\w\.]+))?'")

    spans_to_remove = []  # type: List[Span]

    for lineno, grouped in itertools.groupby(messages, lambda x: x.line):
        line_messages = list(grouped)

        col = min(x.col for x in line_messages)
        node = module.get_leaf_for_position((lineno, col)).parent

        if len(node.get_paths()) == len(line_messages):
            start_pos = get_start_pos(node)
            end_pos = node.end_pos
            spans_to_remove.append((start_pos, end_pos))
            continue

        for message in line_messages:
            match = message_regex.search(message.message)
            if match is None:
                raise ValueError("Unable to extract import name from message {!r}".format(
                    message.message,
                ))

            import_name = match.group(1).split('.')
            import_as_name = match.group(3)

            if import_name[:node.level] != [''] * node.level:
                raise ValueError("Source level is shallower than message")

            if import_name[node.level] == ['']:
                raise ValueError("Source level is deeper than message")

            import_name = import_name[node.level:]

            found_path = find_path(node, import_name, import_as_name)

            last_part = found_path[-1]
            assert last_part.parent is not None  # placate mypy
            if last_part.parent.parent == node:
                # We're removing something like `bar as spam` from
                #   from foo import bar as spam, quox
                assert not import_as_name, "Expected renamed import, but didn't find it"
                node_to_remove = last_part
            else:
                # We're removing something like `quox` from
                #   from foo import bar as spam, quox
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

    flake8 = Flake8()
    flake8.initialize(args + ['--format', FLAKE8_FORMAT])

    # Only run for the checks we can do anything about:
    decider = flake8.guide.decider
    flake8.options.select = [
        code
        for code in FIXERS.keys()
        if decider.decision_for(code) == Decision.Selected
    ]
    flake8.run_checks()
    flake8.report()

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


def run(args: argparse.Namespace) -> None:
    all_error_details = run_flake8(args.flake8_args)

    for filepath, error_details in all_error_details.items():
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
