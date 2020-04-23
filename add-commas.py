#!/usr/bin/env python

import sys
import itertools
import subprocess

flake_output = subprocess.run(
    ['flake8'] + sys.argv[1:],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
).stdout

missing_commas = [
    x.split(':')[:3]
    for x in flake_output.decode('utf-8').splitlines()
    if 'C812' in x
]

for filepath, positions in itertools.groupby(missing_commas, lambda x: x[0]):
    with open(filepath, mode='r+') as f:
        lines = f.readlines()

        for _, lineno_str, col_str in positions:
            lineno = int(lineno_str) - 1
            col = int(col_str) - 1

            text = lines[lineno]
            lines[lineno] = text[:col] + ',' + text[col:]

        f.seek(0)
        f.write(''.join(lines))
        f.truncate()
