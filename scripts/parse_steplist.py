#!/usr/bin/env python

import sys

from optparse import OptionParser

from pypeline import parse_steplist_str

usage = '%prog [options] <steplist string>'
desc = "Wrapper around pypeline.parse_steplist for use in shell scripts, prints " \
"expanded indices from strings like 1-3,4,9,10-12, etc. to screen."
parser = OptionParser(usage=usage,description=desc)
parser.add_option('-s','--separator',dest='sep',default=' ',help='separator character between expanded steplist values [default: \' \']')

if __name__ == '__main__' :

    opts, args = parser.parse_args(sys.argv[1:])

    if len(args) != 1 :
        parser.error('Exactly 1 non-option argument is required')

    steplist_str = args[0]
    steplist = parse_steplist_str(steplist_str)

    sys.stdout.write(opts.sep.join([str(x) for x in steplist]))
