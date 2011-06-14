#!/usr/bin/env python
from distutils.core import setup

scripts = ['scripts/getopts.py',
           'scripts/steplist.py',
           'scripts/parse_steplist.py'
          ]

setup(name='pypeline',
      version='1.2',
      py_modules=['pypeline'],
      scripts=scripts,
    )
