import Scripting
Scripting.g_gz = 'gz'

srcdir = '.'
blddir = 'build'

VERSION = '0.3.0'
APPNAME = 'bioutil'

def set_options(opt) :
	opt.tool_options('python')

	opt.sub_options('src')
	opt.sub_options('bin')

def configure(conf) :

	conf.check_tool('python')
	conf.check_python_version((2,4,2))

	conf.sub_config('src')
	conf.sub_config('bin')

def build(bld) :
	bld.add_subdirs('src')
	bld.add_subdirs('bin')
