#!/usr/bin/env python
from pypeline import Pypeline, ProcessPypeStep, PythonPypeStep

if __name__ == '__main__' :

    pipeline = Pypeline(log='simple_example.log', ignore_failure=True)

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
    def rm_stuff() :
        import glob
        from subprocess import call
        txt_fns = glob.glob('*.txt')
        for fn in txt_fns :
            call('rm %s'%fn,shell=True)
        return True
    steps.append(PythonPypeStep('Cleanup',rm_stuff))

    # step 5 - intentionally fail
    def epic_fail() :
        return False
    steps.append(PythonPypeStep('Cheerfully Ignore Failure',epic_fail))

    # step 6 - whistle a happy tune
    steps.append(ProcessPypeStep('Whistle a Happy Tune','echo Whistling a happy tune'))

    pipeline.add_steps(steps)
    pipeline.run(interactive=True)
