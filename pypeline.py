import sys
from subprocess import call

try :
    from terminalcontroller import *
except ImportError : # no terminalcontroller package found, replace functions with sys.stderr
    import datetime
    # use closures
    def make_msg_call(prefix) :
        def msg(x) :
            now = datetime.datetime.now()
            fmt_msg = '%s[%s]: %s\n'%(prefix,now.strftime('%Y/%m/%d-%H:%M:%S'),x)
            sys.stderr.write(fmt_msg)
        return fmt_msg

    debug = make_msg_call('DEBUG')
    info = make_msg_call('INFO')
    warn = make_msg_call('WARN')
    error = make_msg_call('ERROR')


def get_steplist(pipeline) :
    info(pipeline.name)
    for i,s in enumerate(pipeline.steps) :
        sys.stderr.write('%d: %s\n'%(i,s.name))
    steplist_str = raw_input('Execute which steps (e.g. 1-2,4,6) [all]:')
    if steplist_str == '' :
        steplist = range(len(pipeline.steps))
    else :
        steplist = []
        for arg in steplist_str.split(',') :
            if arg.find('-') != -1 : # we have a span argument
                st,sp = arg.split('-')
                try :
                    st,sp = int(st),int(sp)
                except :
                    sys.stderr.write('Invalid span argument, aborting: %s'%arg)
                    sys.exit(1)
                steplist.extend(range(st,sp+1))
            else :
                try :
                    st = int(arg)
                except :
                    sys.stderr.write('Invalid span argument, aborting: %s'%arg)
                    sys.exit(1)
                steplist.append(st)

    steplist.sort()
    return steplist


class PypelineException(Exception) : pass


class Pypeline :
    def __init__(self,name=None,log=None,ignore_failure=False) :
        self.steps = []
        self.log = open(log,'w') if type(log) is str else log
        self.name = 'Pipeline' if name is None else name
        self.ignore_failure = ignore_failure

    def add_step(self,step,pos=None) :
        pos = len(self.steps) if pos is None else pos
        self.steps.insert(pos,step)

    def add_steps(self,steps,pos=None) :
        pos = len(self.steps) if pos is None else pos
        for i,s in enumerate(steps) :
            self.add_step(s,pos=pos+i)

    def run(self,interactive=False,steplist=None) :
        if interactive :
            steplist = get_steplist(self)
        else :
            if steplist is not None :
                steplist.sort() # just in case
            else :
                steplist = range(len(self.steps)) # do all steps

        results = []
        for i,s in enumerate(self.steps) :
            if i in steplist :
                r = s.execute(fd=self.log)
            else :
                r = s.skip(fd=self.log)
            results.append(r)
            if not self.ignore_failure and r is False :
                sys.stderr.write('Step %d failed, aborting pipeline\n'%i)
                break

        if self.log is not None :
            self.log.close()

class PypeStep :
    """Base pipeline step that doesn't do anything on its own.  Subclass and override
the execute() method for custom functionality or use a canned class from this
package (e.g. ProcessPypeStep)."""

    def __init__(self,name,silent=False,precondition=lambda:True,postcondition=lambda:True) :
        self.name = name
        self.silent = silent
        self.precondition = precondition
        self.postcondition = postcondition

    def precondition_met(self) :
        return self.precondition()

    def postcondition_met(self) :
        return self.postcondition()

    def execute(self) :
        raise PypelineException('PypeStep.execute() method is not defined, override in subclasses of PypeStep')

    def skip(self) :
        pass # do nothing by default

    def _info_msg(self,msg,fd=None) :
        if not self.silent :
            r = info(msg)
            if fd is not None :
                fd.write(str(r))

    def _print_msg(self,msg,fd=None) :
        if not self.silent :
            r = msg+'\n'
            sys.stderr.write(r)
            if fd is not None :
                fd.write(r)


class PythonPypeStep(PypeStep) :
    """A pipeline step that accepts a python callable as its action"""

    def __init__(self,name,callable,callable_args=(),skipcallable=lambda:True,skipcallable_args=(),silent=False,precondition=lambda:True,postcondition=lambda:True) :
        PypeStep.__init__(self,name,silent=silent,precondition=precondition,postcondition=postcondition)
        self.callable = callable
        self.callable_args = callable_args
        self.skipcallable = skipcallable
        self.skipcallable_args = skipcallable_args

    def execute(self,fd=None) :
        self._info_msg(self.name,fd)
        return self.callable(*self.callable_args)

    def skip(self,fd=None) :
        self._info_msg(self.name+' SKIPPED',fd)
        return self.skipcallable(*self.skipcallable_args)


class ProcessPypeStep(PypeStep) :
    """A pipeline step that wrap subprocess.Popen calls for a command line utility"""

    def __init__(self,name,calls,skipcalls=[],silent=False,precondition=lambda:True,postcondition=lambda:True,env={},ignore_failure=False) :
        PypeStep.__init__(self,name,silent=silent,precondition=precondition,postcondition=postcondition)
        self.calls = calls if type(calls) is list else [calls]
        self.skipcalls = skipcalls if type(skipcalls) is list else [skipcalls]
        self.env = env
        self.ignore_failure = ignore_failure

    def execute(self,fd=None) :
        self._info_msg(self.name,fd)
        r = 0
        for cmd in self.calls :
            self._print_msg('\t'+cmd,fd)
            r = call(cmd,shell=True,env=self.env)
            if not self.ignore_failure and r != 0 : # presumed failure
                break
        return self.ignore_failure or r == 0

    def skip(self,fd=None) :
        self._info_msg(self.name+' SKIPPED',fd)
        r = 0
        for cmd in self.skipcalls :
            self._print_msg('\t'+cmd,fd)
            r = call(cmd,shell=True,env=self.env)
            if not self.ignore_failure and r != 0 : # presumed failure
                break
        return self.ignore_failure or r == 0
