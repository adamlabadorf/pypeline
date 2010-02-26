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
			sys.stderr.write('%s[%s]: %s\n'%(prefix,now.strftime('%Y/%m/%d-%H:%M:%S'),x))
		return msg

	debug = make_msg_call('DEBUG')
	info = make_msg_call('INFO')
	warn = make_msg_call('WARN')
	error = make_msg_call('ERROR')

def get_steplist(pipeline) :
	info('Pipeline:')
	for i,s in enumerate(pipeline.steps) :
		sys.stderr.write('%d: %s\n'%(i,s.name))
	steplist_str = raw_input('Execute which steps [all]:')
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
	def __init__(self) :
		self.steps = []

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
			steplist.sort() # just in case

		for i,s in enumerate(self.steps) :
			if i in steplist :
				s.execute()
			else :
				s.skip()

class PypeStep :
	"""Base pipeline step that doesn't do anything on its own.  Subclass and override the execute() method for custom functionality or use a canned class from this package (e.g. ProcessPypeStep)."""
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

class ProcessPypeStep(PypeStep) :
	"""A pipeline step that wrap subprocess.Popen calls for a command line utility"""
	def __init__(self,name,calls,skipcalls=[],silent=False,precondition=lambda:True,postcondition=lambda:True) :
		PypeStep.__init__(self,name,silent=silent,precondition=precondition,postcondition=postcondition)
		self.calls = calls if type(calls) is list else [calls]
		self.skipcalls = skipcalls if type(skipcalls) is list else [skipcalls]

	def execute(self) :
		for cmd in self.calls :
			r = call(cmd,shell=True)

	def skip(self) :
		for cmd in self.skipcalls :
			r = call(cmd,shell=True)


