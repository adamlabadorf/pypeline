import os
import re
import select
import sys
import threading

from subprocess import call


try :
    from terminalcontroller import *
except ImportError : # no terminalcontroller package found, replace functions with sys.stderr
    import datetime
    # use closures
    def make_msg_call(prefix) :
        def msg(x,fd=None) :
            now = datetime.datetime.now()
            fmt_msg = '%s[%s]: %s\n'%(prefix,now.strftime('%Y/%m/%d-%H:%M:%S'),x)
            sys.stderr.write(fmt_msg)
            return fmt_msg
        return msg

    debug = make_msg_call('DEBUG')
    info = make_msg_call('INFO')
    warn = make_msg_call('WARN')
    error = make_msg_call('ERROR')

def write_identity(st,fd=None) :
    if fd :
        fd.write(st)
    return st

class Tee(threading.Thread) :

    def __init__(self,wlist,group=None, target=None, name=None, args=(), kwargs={}) :
        threading.Thread.__init__(self,group,target,name,args,kwargs)
        self.r, self.w = os.pipe()
        self.in_r = os.fdopen(self.r,'r')
        self.out_w = os.fdopen(self.w,'w')
        self.wlist = wlist
        self.daemon = True
        self.stop = False

    def run(self) :
        while not self.stop :
            self.out_w.flush()
            i,o,e = select.select([self.in_r],[],[],1)
            if len(i) == 1 :
                done = False
                w_str = ''
                while not done :
                    o_str = os.read(i[0].fileno(),512)
                    if len(o_str) < 512 :
                        done = True
                    w_str += o_str
                for w in self.wlist :
                    w.write(w_str)
                    w.flush()
        self.in_r.close()
        self.out_w.close()


def get_steplist(pipeline) :

    for i,s in enumerate(pipeline.steps) :
        pipeline.printout('%d: %s\n'%(i,s.name))

    prompt = 'Execute which steps (e.g. 1-2,4,6) [all]:'

    sys.stderr.write(prompt)
    #steplist_str = raw_input(prompt)
    steplist_str = sys.stdin.readline()

    pipeline.printout(prompt+steplist_str+'\n',exclude=[sys.stderr])

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
                    pipeline.error('Invalid span argument, aborting: %s'%arg)
                    sys.exit(1)
                steplist.extend(range(st,sp+1))
            else :
                try :
                    st = int(arg)
                except :
                    pipeline.error('Invalid span argument, aborting: %s'%arg)
                    sys.exit(1)
                steplist.append(st)

    steplist.sort()
    return steplist


class PypelineException(Exception) : pass


class Pypeline :
    def __init__(self,name=None,log=None,ignore_failure=False) :
        self.steps = []
        out_fds = [sys.stderr]
        if log :
            out_fds.append(open(log,'a'))
        self.tee_t = Tee(out_fds)
        self.out_f = self.tee_t.out_w
        self.tee_t.start()

        self.name = 'Pipeline' if name is None else name
        self.ignore_failure = ignore_failure

        self.announce(self.name)

    def add_step(self,step,pos=None) :
        pos = len(self.steps) if pos is None else pos
        step.pipeline = self
        self.steps.insert(pos,step)

    def add_steps(self,steps,pos=None) :
        pos = len(self.steps) if pos is None else pos
        for i,s in enumerate(steps) :
            self.add_step(s,pos=pos+i)

    def announce(self,st) :
        self._write_output(st,announce)

    def info(self,st) :
        self._write_output(st,info)

    def warn(self,st) :
        self._write_output(st,warn)

    def error(self,st) :
        self._write_output(st,error)

    def printout(self,st,exclude=[]) :
        self._write_output(st,write_identity,exclude=exclude)

    def _write_output(self,st,fn,exclude=[]) :
        r = fn(st,fd=None)
        for fd in self.tee_t.wlist :
            if fd in exclude :
                continue
            elif fd in (sys.stdout, sys.stderr) :
                fn(st,fd=fd)
            else :
                fd.write(r)

    def run(self,interactive=False,steplist=None) :

        try :
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
                    r = s.execute()
                else :
                    r = s.skip()
                results.append(r)
                if not self.ignore_failure and r is False :
                    self.error('Step %d failed, aborting pipeline\n'%i)
                    break
        except KeyboardInterrupt :
            self.printout('\nPipeline interrupted by user, aborting\n')
        finally :
            self.tee_t.stop = True

        return results


def _check_conditions(f) :
    """Decorator function for PypeStep subclass execute methods. Should
    not be invoked by the user."""
    def nf(self,*args,**kwargs):
        self.check_precondition()
        ret = f(self,*args,**kwargs)
        self.check_postcondition()
        return ret
    return nf


class PypeStep :
    """Base pipeline step that doesn't do anything on its own.  Subclass and override
the execute() method for custom functionality or use a canned class from this
package (e.g. ProcessPypeStep)."""

    def __init__(self,name,silent=False,precondition=lambda:True,postcondition=lambda:True,ignore_failure=False) :
        self.name = name
        self.silent = silent
        self.precondition = precondition
        self.postcondition = postcondition
        self.ignore_failure = ignore_failure

    def check_precondition(self) :
        precond_met = self.precondition() == True
        if not precond_met :
            if ignore_failure :
                self._print_msg('\tPrecondition not met but ignoring failures, skipping')
            else :
                self._print_msg('\tPrecondition not met, dying')
                raise PypelineException('Precondition not met for step %s'%self.name)

    def check_postcondition(self) :
        postcond_met = self.postcondition() == True
        if not postcond_met and not ignore_failure :
            if ignore_failure :
                self._print_msg('\tPrecondition not met but ignoring failures, skipping')
            else :
                self._print_msg('\tPrecondition not met, dying')
                raise PypelineException('Precondition not met for step %s'%self.name)

    @_check_conditions
    def execute(self) :
        raise PypelineException('PypeStep.execute() method is not defined, override in subclasses of PypeStep')

    def skip(self) :
        pass # do nothing by default

    def _info_msg(self,msg) :
        if not self.silent :
            self.pipeline.info(msg)

    def _print_msg(self,msg) :
        if not self.silent :
            r = msg+'\n'
            self.pipeline.printout(r)


class PythonPypeStep(PypeStep) :
    """A pipeline step that accepts a python callable as its action"""

    def __init__(self,name,callable,
                 callable_args=(),
                 callable_kwargs={},
                 skipcallable=lambda:None,
                 skipcallable_args=(),
                 silent=False,
                 precondition=lambda:True,
                 postcondition=lambda:True,
                 ignore_failure=False) :
        PypeStep.__init__(self,name,
                          silent=silent,
                          precondition=precondition,
                          postcondition=postcondition,
                          ignore_failure=ignore_failure)
        self.callable = callable
        self.callable_args = callable_args
        self.callable_kwargs = callable_kwargs
        self.skipcallable = skipcallable
        self.skipcallable_args = skipcallable_args

    @_check_conditions
    def execute(self) :
        self._info_msg(self.name)

        # swap out sys.stdout, sys.stderr for pipeline's fd object
        old_stdout, old_stderr = sys.stdout, sys.stderr
        #print 'switching fds'
        #sys.stdout, sys.stderr = self.pipeline.tee_t.out_w, self.pipeline.tee_t.out_w
        #print 'done switching fds'

        # who you gonna call?
        r = self.callable(*self.callable_args,**self.callable_kwargs)

        # put back original sys file descriptors
        sys.stdout, sys.stderr = old_stdout, old_stderr
        return r

    def skip(self) :
        self._info_msg(self.name+' SKIPPED')
        return self.skipcallable(*self.skipcallable_args)


class ProcessPypeStep(PypeStep) :
    """A pipeline step that wrap subprocess.Popen calls for a command line utility"""

    def __init__(self,name,calls,
                 skipcalls=None,
                 silent=False,
                 precondition=lambda:True,
                 postcondition=lambda:True,
                 env=None,
                 ignore_failure=False) :
        PypeStep.__init__(self,name,
                          silent=silent,
                          precondition=precondition,
                          postcondition=postcondition,
                          ignore_failure = ignore_failure)
        self.calls = calls if type(calls) is list else [calls]
        skipcalls = skipcalls or []
        try :
            iter(skipcalls)
        except TypeError :
            skipcalls = tuple(skipcalls)
        self.skipcalls = skipcalls
        self.env = env or {}

    @_check_conditions
    def execute(self) :
        self._info_msg(self.name)
        r = 0

        for cmd in self.calls :
            self._print_msg('\t'+cmd)
            # filter out extra whitespace
            cmd = cmd.strip()
            cmd = re.sub(r'\s+',r' ',cmd)
            r = call(cmd,shell=True,env=self.env,
                     stdout=self.pipeline.tee_t.out_w,
                     stderr=self.pipeline.out_f)
            if not self.ignore_failure and r != 0 : # presumed failure
                break

        return self.ignore_failure or r == 0

    def skip(self) :
        self._info_msg(self.name+' SKIPPED')
        r = 0
        for cmd in self.skipcalls :
            self._print_msg('\t'+cmd)
            r = call(cmd,shell=True,env=self.env,stdout=self.out_f,stderr=self.out_f)
            if not self.ignore_failure and r != 0 : # presumed failure
                break
        return self.ignore_failure or r == 0
