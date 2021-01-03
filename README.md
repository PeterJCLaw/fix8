# Fix8

[![CircleCI](https://circleci.com/gh/PeterJCLaw/fix8.svg?style=svg)](https://circleci.com/gh/PeterJCLaw/fix8)

Automatic fix for Python linting issues found by [Flake8](https://flake8.pycqa.org/).

## Fixes

* `F401`: Unused imports are removed
* `C812`, `C813`, `C814`, `C815`, `C816`: Trailing commas are added

## Install

``` bash
pip install fix8
```

## Usage

`fix8` wraps `flake8`, so takes the same arguments. The easist way to use it is
to pass the files or directories you want fixed directly to it:

``` bash
fix8 project/ that.py this.py
```

### Wrappers

If you have a large project you may want to wrap it, something like this:

``` bash
fix8-local() {
    git diff --name-only --diff-filter=d | grep '\.py$' | sort --unique | xargs --no-run-if-empty fix8
}
```

This can be paired with `isort` to do both fixes with a single command:

``` bash
# Put these functions in your `.bashrc` or similar
run-py-local() {
    git diff --name-only --diff-filter=d | grep '\.py$' | sort --unique | xargs --no-run-if-empty "$@"
}

fix8-local() {
    run-py-local fix8 && run-py-local isort
}

# Usage is then just this, but will detect and fix any changes that might need fixing
$ fix8-local
```
