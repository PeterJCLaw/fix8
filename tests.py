#!/usr/bin/env python3

import textwrap
import unittest
from pathlib import Path

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

        parsed_errors = fix8.run_flake8(['-'], _input=content.encode())
        error_details = parsed_errors[Path('stdin')]
        new_content = fix8.process_errors(error_details, content)

        self.assertEqual(expected_output, new_content, message)


class TestFixesF401(BaseFixesTestCast):
    def test_single_import(self) -> None:
        self.assertFixes(
            '''
            import os
            ''',
            '\n\n',
        )

    def test_first_import_from_multi(self) -> None:
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

    def test_middle_import_from_multi(self) -> None:
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

    def test_last_import_from_multi(self) -> None:
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

    def test_single_from_import(self) -> None:
        self.assertFixes(
            '''
            from os import path
            ''',
            '\n\n',
        )

    def test_single_name_in_from_import(self) -> None:
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


if __name__ == '__main__':
    unittest.main(__name__)
