#!/usr/bin/env python

import sys
import json
import os
from optparse import OptionParser
from subprocess import Popen

from pypeline import MultiLineHelpFormatter as MF

template = """
OPT_SPEC='
{
"NAME": "",
"DESC": "",
"ARGS": ["",""],
"OPTS": {
    "SOMEARG":{"SHORT":"-s","LONG":"--some-arg","DEFAULT":3,"ACTION":"store_true","HELP":"some arg that does something"}
    }
}'
OUTPUT=$(echo $OPT_SPEC | getopts.py -- $@)
GETOPTS_RET=$?
if [ $GETOPTS_RET -ne 0 ]; then
    exit 1
fi
$OUTPUT
"""


s_usage = '%prog [<arguments>] < <json text>'
s_desc = """A wrapper around python's optparse.OptionParser for use in shell
scripts.  Option specification is provided as a JSON string as the first
argument with format:

{
"NAME": "stuff",
"DESC": "Does some stuff",
"ARGS": ["arg1","arg2"],
"OPTS": {
    "SOMEARG":{"SHORT":"-s","LONG":"--some-arg","DEFAULT":3,"HELP":"some arg that does something"}
    }
}

NAME is required.  ARGS, if specified, must be a list of identifiers that are
the desired shell variable names of the positional arguments. If OPTS are
supplied, the key (e.g. SOMEARG) will be the resulting variable composed into
a source-able output, and either SHORT, LONG, or both are required.  In shell
scripts, use like this (e.g. bash, assumes OPT_SPEC variable contains json
example above):

#!/bin/bash
# OPT_SPEC definition
$(echo $OPT_SPEC | getopts.py $@)"""
s_parser = OptionParser(usage=s_usage,description=s_desc,formatter=MF())
s_parser.add_option('--template',dest='templ',action='store_true',help='print to stdout a template that can be used in bash scripts and exit')

if __name__ == '__main__' :
    

    opts, args = s_parser.parse_args(sys.argv[1:])
    if opts.templ :
        sys.stdout.write(template)
        sys.exit(0)

    json_str = sys.stdin.read()
    opt_obj =  json.loads(json_str)

    # set some stuff
    name = opt_obj.get('NAME',None)
    if name is None :
        sys.stderr.write('Must specify NAME field when using getopts.py, exiting\n')
        sys.exit(1)
    args = opt_obj.get('ARGS')
    args_str = ' '.join(["<%s>"%s for s in args]) if args is not None else None
    usage = "%s [options] %s"%(name,args_str)
    desc = opt_obj.get('DESC','You should write a description!')

    # build the parser
    parser = OptionParser(usage=usage,description=desc)
    opt_names = []
    for k,opt in opt_obj.get('OPTS',{}).items() :
        opt_strs = []
        short, long = opt.get('SHORT'), opt.get('LONG')
        if short : opt_strs.append(short)
        if long : opt_strs.append(long)

        if len(opt_strs) == 0 :
            sys.stderr.write("Options must have either SHORT, LONG, or both option names specified\n")
            sys.exit(2)
        d = {'dest':k}
        if opt.get('ACTION') : d['action'] = opt.get('ACTION')
        if opt.get('DEFAULT') : d['default'] = opt.get('DEFAULT')
        if opt.get('HELP') : d['help'] = opt.get('HELP')
        parser.add_option(*opt_strs,**d)
        opt_names.append(k)

    # parse
    #if '-h' in sys.argv[1:] or '--help' in sys.argv[1:] :
    #    parser.print_help(file=sys.stderr)
    #    sys.exit(1)
    
    startargs_i = sys.argv.index('--') if '--' in sys.argv else 1
    startargs = sys.argv[startargs_i+1:] if startargs_i < len(sys.argv) else []
    if '-h' in startargs or '--help' in startargs :
        parser.print_help(sys.stderr)
        sys.exit(1)
    opts, pargs = parser.parse_args(startargs)

    if len(pargs) != len(args) :
        parser.error('Exactly %d non-option arguments are required'%len(args))

    # print out the args as declarations bash/tcsh can understand
    shell = os.path.basename(os.environ.get('SHELL','bash'))
    if shell in ['csh','sh','tcsh'] :
        output_str = '\tsetenv %s %s\n'
    else : # assume bash
        output_str = '\texport %s=%s\n'
        

    output = zip(args,pargs)+[(k,getattr(opts,k)) for k in opt_names]
    for name, val in output :
        if ' ' in str(val) : val = '"%s"'%val
        sys.stdout.write(output_str%(name,val))
