#!/usr/bin/env python
from pypeline import Pypeline, ProcessPypeStep

if __name__ == '__main__' :

	pipeline = Pypeline()

	steps = []

	# step 1 - list the current directory
	ls_fn = 'ls_out.txt'
	steps.append(ProcessPypeStep('Get directory file list','ls -1d > %s'%ls_fn))

	# step 2 - do a word count
	wc_fn = 'wc_out.txt'
	steps.append(ProcessPypeStep('Get wordcount','wc %s > %s'%(ls_fn,wc_fn)))

	# step 3 - sort the file and output
	steps.append(ProcessPypeStep('Sort wordcount','sort -n %s'%wc_fn))

	# step 4 - cleanup files
	steps.append(ProcessPypeStep('Cleanup',"rm %s"%(" ".join([ls_fn,wc_fn]))))

	pipeline.add_steps(steps)
	pipeline.run(interactive=True)
