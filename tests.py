#!/usr/bin/env python3

import textwrap
import unittest
from pathlib import Path
from unittest import mock

import fix8


class BaseFixesTestCast(unittest.TestCase):
    def assertFixes(
        self,
        content: str,
        expected_output: str,
        *,
        message: str = "Bad fixes"
    ) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])
        expected_output = textwrap.dedent(expected_output[1:])

        with mock.patch('flake8.utils.stdin_get_value', return_value=content):
            parsed_errors = fix8.run_flake8(['-'])

        error_details = parsed_errors[Path('stdin')]
        new_content = fix8.process_errors(error_details, content)

        self.assertEqual(expected_output, new_content, message)


class TestFixesF401(BaseFixesTestCast):
    def test_absolute_single_import(self) -> None:
        self.assertFixes(
            '''
            import os
            ''',
            '\n',
        )

    def test_absolute_multiple_imports(self) -> None:
        self.assertFixes(
            '''
            import os, sys
            ''',
            '\n',
        )

    def test_absolute_first_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            import os, sys
            sys.stdout.write('')
            ''',
            '''
            import sys
            sys.stdout.write('')
            ''',
        )

    def test_absolute_middle_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            import io, os, sys
            io.StringIO()
            sys.stdout.write('')
            ''',
            '''
            import io, sys
            io.StringIO()
            sys.stdout.write('')
            ''',
        )

    def test_absolute_middle_as_name_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            import io, os as _os, sys
            io.StringIO()
            sys.stdout.write('')
            ''',
            '''
            import io, sys
            io.StringIO()
            sys.stdout.write('')
            ''',
        )

    def test_absolute_last_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            import sys, os
            sys.stdout.write('')
            ''',
            '''
            import sys
            sys.stdout.write('')
            ''',
        )

    def test_absolute_single_from_import(self) -> None:
        self.assertFixes(
            '''
            from os import path
            ''',
            '\n',
        )

    def test_absolute_multiple_from_imports(self) -> None:
        self.assertFixes(
            '''
            from os import path
            ''',
            '\n',
        )

    def test_absolute_first_name_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import basename, dirname
            dirname(__file__)
            ''',
            '''
            from os.path import dirname
            dirname(__file__)
            ''',
        )

    def test_absolute_middle_name_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import abspath, basename, dirname
            abspath(dirname(__file__))
            ''',
            '''
            from os.path import abspath, dirname
            abspath(dirname(__file__))
            ''',
        )

    def test_absolute_last_name_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import dirname, basename
            dirname(__file__)
            ''',
            '''
            from os.path import dirname
            dirname(__file__)
            ''',
        )

    def test_absolute_last_two_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import dirname, basename, realpath
            dirname(__file__)
            ''',
            '''
            from os.path import dirname
            dirname(__file__)
            ''',
        )

    def test_absolute_first_and_last_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import basename, dirname, realpath
            dirname(__file__)
            ''',
            '''
            from os.path import dirname
            dirname(__file__)
            ''',
        )

    def test_absolute_first_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import (
                basename,
                dirname,
            )
            dirname(__file__)
            ''',
            '''
            from os.path import (
                dirname,
            )
            dirname(__file__)
            ''',
        )

    def test_absolute_middle_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import (
                abspath,
                basename,
                dirname,
            )
            abspath(dirname(__file__))
            ''',
            '''
            from os.path import (
                abspath,
                dirname,
            )
            abspath(dirname(__file__))
            ''',
        )

    def test_absolute_last_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import (
                dirname,
                basename,
            )
            dirname(__file__)
            ''',
            '''
            from os.path import (
                dirname,
            )
            dirname(__file__)
            ''',
        )

    def test_relative_module_single_import(self) -> None:
        self.assertFixes(
            '''
            from . import os
            ''',
            '\n',
        )

    def test_relative_module_multiple_imports(self) -> None:
        self.assertFixes(
            '''
            from . import os, sys
            ''',
            '\n',
        )

    def test_relative_module_first_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            from . import os, sys
            sys.stdout.write('')
            ''',
            '''
            from . import sys
            sys.stdout.write('')
            ''',
        )

    def test_relative_module_middle_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            from . import io, os, sys
            io.StringIO()
            sys.stdout.write('')
            ''',
            '''
            from . import io, sys
            io.StringIO()
            sys.stdout.write('')
            ''',
        )

    def test_relative_module_last_import_in_multi(self) -> None:
        self.assertFixes(
            '''
            from . import sys, os
            sys.stdout.write('')
            ''',
            '''
            from . import sys
            sys.stdout.write('')
            ''',
        )

    def test_relative_single_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os import path
            ''',
            '\n',
        )

    def test_relative_first_name_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import basename, dirname
            dirname(__file__)
            ''',
            '''
            from .os.path import dirname
            dirname(__file__)
            ''',
        )

    def test_relative_middle_name_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import abspath, basename, dirname
            abspath(dirname(__file__))
            ''',
            '''
            from .os.path import abspath, dirname
            abspath(dirname(__file__))
            ''',
        )

    def test_relative_last_name_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import dirname, basename
            dirname(__file__)
            ''',
            '''
            from .os.path import dirname
            dirname(__file__)
            ''',
        )

    def test_relative_module_multiple_imports_wrapped(self) -> None:
        self.assertFixes(
            '''
            from . import (
                os,
                sys,
            )
            ''',
            '\n',
        )

    def test_relative_first_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import (
                basename,
                dirname,
            )
            dirname(__file__)
            ''',
            '''
            from .os.path import (
                dirname,
            )
            dirname(__file__)
            ''',
        )

    def test_relative_middle_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import (
                abspath,
                basename,
                dirname,
            )
            abspath(dirname(__file__))
            ''',
            '''
            from .os.path import (
                abspath,
                dirname,
            )
            abspath(dirname(__file__))
            ''',
        )

    def test_relative_middle_as_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import (
                abspath,
                basename
                as
                bn,
                dirname,
            )
            abspath(dirname(__file__))
            ''',
            '''
            from .os.path import (
                abspath,
                dirname,
            )
            abspath(dirname(__file__))
            ''',
        )

    def test_relative_last_name_in_wrappped_from_import(self) -> None:
        self.assertFixes(
            '''
            from .os.path import (
                dirname,
                basename,
            )
            dirname(__file__)
            ''',
            '''
            from .os.path import (
                dirname,
            )
            dirname(__file__)
            ''',
        )

    def test_renamed_duplicate_original_used_when_as_first(self) -> None:
        self.assertFixes(
            '''
            from foo import bar as spam, bar
            bar()
            ''',
            '''
            from foo import bar
            bar()
            ''',
        )

    def test_renamed_duplicate_rename_used_when_as_first(self) -> None:
        self.assertFixes(
            '''
            from foo import bar as spam, bar
            spam()
            ''',
            '''
            from foo import bar as spam
            spam()
            ''',
        )

    def test_renamed_duplicate_original_used_when_as_second(self) -> None:
        self.assertFixes(
            '''
            from foo import bar, bar as spam
            bar()
            ''',
            '''
            from foo import bar
            bar()
            ''',
        )

    def test_renamed_duplicate_rename_used_when_as_second(self) -> None:
        self.assertFixes(
            '''
            from foo import bar, bar as spam
            spam()
            ''',
            '''
            from foo import bar as spam
            spam()
            ''',
        )

    def test_indented_import(self) -> None:
        self.assertFixes(
            '''
            def circular():
                from foo import bar, bar as spam
                spam()
            ''',
            '''
            def circular():
                from foo import bar as spam
                spam()
            ''',
        )


class TestMergeSpans(unittest.TestCase):
    def test_separate(self) -> None:
        spans = [
            ((1, 1), (2, 1)),
            ((3, 1), (4, 1)),
            ((5, 1), (6, 1)),
        ]

        expected_output = spans.copy()

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_first_two_overlap(self) -> None:
        spans = [
            ((1, 1), (2, 10)),
            ((2, 1), (4, 1)),
            ((5, 1), (6, 1)),
        ]

        expected_output = [
            ((1, 1), (4, 1)),
            ((5, 1), (6, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_last_two_overlap(self) -> None:
        spans = [
            ((1, 1), (2, 1)),
            ((3, 1), (5, 5)),
            ((5, 1), (6, 1)),
        ]

        expected_output = [
            ((1, 1), (2, 1)),
            ((3, 1), (6, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_first_completely_overlaps_second(self) -> None:
        spans = [
            ((1, 1), (2, 10)),
            ((2, 1), (2, 5)),
            ((5, 1), (6, 1)),
        ]

        expected_output = [
            ((1, 1), (2, 10)),
            ((5, 1), (6, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_first_and_last_overlap(self) -> None:
        spans = [
            ((2, 1), (4, 1)),
            ((5, 1), (6, 1)),
            ((1, 1), (2, 10)),
        ]

        expected_output = [
            ((1, 1), (4, 1)),
            ((5, 1), (6, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_last_overlaps_with_all_others(self) -> None:
        spans = [
            ((1, 1), (2, 10)),
            ((3, 1), (4, 1)),
            ((2, 1), (6, 1)),
        ]

        expected_output = [
            ((1, 1), (6, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_overlap_three_of_four(self) -> None:
        spans = [
            ((1, 1), (2, 10)),
            ((1, 1), (4, 1)),
            ((1, 1), (6, 1)),
            ((6, 1), (10, 1)),
        ]

        expected_output = [
            ((1, 1), (10, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))

    def test_all_overlap(self) -> None:
        spans = [
            ((1, 1), (2, 10)),
            ((1, 1), (3, 1)),
            ((2, 1), (6, 1)),
        ]

        expected_output = [
            ((1, 1), (6, 1)),
        ]

        self.assertEqual(expected_output, fix8.merge_overlapping_spans(spans))


if __name__ == '__main__':
    unittest.main(__name__)
