#!/usr/bin/env python

import sys

from optparse import OptionParser

from pypeline import MultiLineHelpFormatter as MF
from pypeline import Pypeline, PythonPypeStep as PyPS, MultiLineHelpFormatter as MF, parse_steplist

usage = '%prog [options] <step name> [<step name> ...]'
description = """Implements a general menu list functionality for use in 
bash scripts.  Prints bash syntax to the stdout that makes a function
*do_step* available that can be used like this:

#!/bin/bash

eval "$(steplist.py -t "Fruit Pipeline" apple orange banana)"
# curr_step, next_step functions and CURRSTEP_INDX now defined

next_step && ./run_apple.sh
next_step && ./run_orange.sh
curr_step && ./run_orange_again.sh
next_step && ./run_banana.sh

"""
parser = OptionParser(usage=usage,description=description,formatter=MF())
parser.add_option('-t','--title',dest='title',default=None,help='title of pipeline')
parser.add_option('-a','--auto',dest='auto',action='store_true',default=None,help='run non-interactively')
parser.add_option('--steplist',dest='steplist',default='',help='with --auto, run specific steps')


if __name__ == '__main__' :

    opts, args = parser.parse_args(sys.argv[1:])

    if len(args) < 1 :
        parser.error('One or more non-option arguments are required')

    steps = []

    run_cond_tmpl = '[ $CURRSTEP_INDX -eq %d ] && echo -e "\033\e[1;37mRunning %s\e[0m" && return 0;'
    for i, arg in enumerate(args) :
        steps.append(PyPS(arg,lambda x: x,(run_cond_tmpl%(i,arg),),silent=True))

    bash_fn_str = """\
CURRSTEP_INDX=-1;
function curr_step {
    %s
    return 1;
};
function next_step {
    let CURRSTEP_INDX=CURRSTEP_INDX+1;
    curr_step;
    RET=$?;
    return $RET;
};"""

    pipeline = Pypeline(opts.title)
    pipeline.add_steps(steps)

    if opts.auto and opts.steplist is not None :
        steplist = parse_steplist(opts.steplist,pipeline)
    else :
        steplist = None

    res = pipeline.run(interactive=not opts.auto,steplist=steplist)
    res = '\n    '.join(filter(lambda x: x is not None, res))

    sys.stdout.write(bash_fn_str%res)
