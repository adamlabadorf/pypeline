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
        return msg

    debug = make_msg_call('DEBUG')
    info = make_msg_call('INFO')
    warn = make_msg_call('WARN')
    error = make_msg_call('ERROR')

class Tee(object):
    """File object that writes to both a file and to stdout, like the unix
       `tee` command"""

    control_chars = ''.join(map(unichr, range(0,32) + range(127,160)))
    control_char_re = re.compile('[%s]' % re.escape(control_chars))

    def __init__(self, name=None, mode='w', fd=None, std_fd=sys.stdout):

        if (name and fd) or (not name and not fd) :
            raise Exception('The name and fd arguments to the Tee class are mutually exclusive')
        elif name :
            self.file = open(name, mode)
        elif fd :
            self.file = fd

        self.std_fd = std_fd

    def __del__(self):
        self.file.close()

    def flush(self) :
        self.file.flush()
        self.std_fd.flush()

    def write(self, data):
        #self.file.write(Tee.control_char_re.sub('',data))
        self.file.write(data)
        self.std_fd.write(data)

def get_steplist(pipeline) :
    r = info(pipeline.name,fd=pipeline.out_f.std_fd)
    pipeline.out_f.file.write(r)
    for i,s in enumerate(pipeline.steps) :
        pipeline.out_f.write('%d: %s\n'%(i,s.name))
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
        if log :
            self.out_f = Tee(fd=log) if hasattr(log,'write') else Tee(name=log,mode='w')
        else :
            self.out_f = sys.stdout

        self.name = 'Pipeline' if name is None else name
        self.ignore_failure = ignore_failure

    def add_step(self,step,pos=None) :
        pos = len(self.steps) if pos is None else pos
        step.out_f = self.out_f
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
                r = s.execute()
            else :
                r = s.skip()
            results.append(r)
            if not self.ignore_failure and r is False :
                sys.stderr.write('Step %d failed, aborting pipeline\n'%i)
                break


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
            r = info(msg,fd=self.out_f.std_fd)
            self.out_f.file.write(str(r))

    def _print_msg(self,msg) :
        if not self.silent :
            r = msg+'\n'
            self.out_f.write(r)


class PythonPypeStep(PypeStep) :
    """A pipeline step that accepts a python callable as its action"""

    def __init__(self,name,callable,
                 callable_args=(),
                 callable_kwargs={},
                 skipcallable=lambda:True,
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
        sys.stdout, sys.stderr = self.out_f, self.out_f

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
                 skipcalls=[],
                 silent=False,
                 precondition=lambda:True,
                 postcondition=lambda:True,
                 env={},
                 ignore_failure=False) :
        PypeStep.__init__(self,name,
                          silent=silent,
                          precondition=precondition,
                          postcondition=postcondition,
                          ignore_failure = ignore_failure)
        self.calls = calls if type(calls) is list else [calls]
        self.skipcalls = skipcalls if type(skipcalls) is list else [skipcalls]
        self.env = env

    @_check_conditions
    def execute(self) :
        self._info_msg(self.name)
        r = 0

        for cmd in self.calls :
            self._print_msg('\t'+cmd)
            r = call(cmd,shell=True,env=self.env,stdout=self.out_f,stderr=self.out_f)
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
