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
    maxDiff = 8000

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

    def test_absolute_first_two_in_from_import(self) -> None:
        self.assertFixes(
            '''
            from os.path import basename, realpath, dirname
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

    def test_absolute_from_kitchen_sink(self) -> None:
        self.assertFixes(
            '''
            from inside import UnusedI1, I1, I2, UnusedI2
            from left import L1, UnusedL1, L2, UnusedL2
            from right import UnusedR1, R1, UnusedR2, R2
            from outside import O1, UnusedO1, UnusedO2, O2
            from mixed_out import MO1, UnusedMO1, MO2, UnusedMO2, MO3
            from mixed_in import UnusedMI1, MI1, UnusedMI2, MI2, UnusedMI3

            from double_inside import UnusedDI0, UnusedDI1, DI1, DI2, UnusedDI2, UnusedDI3
            from double_left import DL1, UnusedDL0, UnusedDL1, DL2, UnusedDL2, UnusedDL3
            from double_right import UnusedDR0, UnusedDR1, DR1, UnusedDR2, UnusedDR3, DR2
            from double_outside import DO1, UnusedDO1, UnusedDO2, DO2
            from double_mixed_out import DMO1, UnusedDMO1, UnusedDMO2, DMO2, UnusedDMO3, UnusedDMO4, DMO3
            from double_mixed_in import UnusedDMI0, UnusedDMI1, DMI1, UnusedDMI2, UnusedDMI3, DMI2, UnusedDMI4, UnusedDMI5

            [I1, I2, L1, L2, R1, R2, O1, O2, MO1, MO2, MO3, MI1, MI2]
            [DI1, DI2, DL1, DL2, DR1, DR2, DO1, DO2, DMO1, DMO2, DMO3, DMI1, DMI2]
            ''',
            '''
            from inside import I1, I2
            from left import L1, L2
            from right import R1, R2
            from outside import O1, O2
            from mixed_out import MO1, MO2, MO3
            from mixed_in import MI1, MI2

            from double_inside import DI1, DI2
            from double_left import DL1, DL2
            from double_right import DR1, DR2
            from double_outside import DO1, DO2
            from double_mixed_out import DMO1, DMO2, DMO3
            from double_mixed_in import DMI1, DMI2

            [I1, I2, L1, L2, R1, R2, O1, O2, MO1, MO2, MO3, MI1, MI2]
            [DI1, DI2, DL1, DL2, DR1, DR2, DO1, DO2, DMO1, DMO2, DMO3, DMI1, DMI2]
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
