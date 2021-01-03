#!/usr/bin/env python

from setuptools import setup  # type: ignore[import]

with open('README.md') as file:
    long_description = file.read()

setup(
    name='fix8',
    version='0.0.1',
    url='https://github.com/PeterJCLaw/fix8',
    project_urls={
        'Documentation': 'https://github.com/PeterJCLaw/fix8/blob/master/READNE.md',
        'Code': 'https://github.com/PeterJCLaw/fix8',
        'Issue tracker': 'https://github.com/PeterJCLaw/fix8/issues',
    },
    description="Automatic fix for Python linting issues found by Flake8",
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="Peter Law",
    author_email='PeterJCLaw@gmail.com',
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Utilities',
    ],
    install_requires=[
        'parso',
    ],
    zip_safe=True,
)
