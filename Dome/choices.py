import os
from os.path import exists

paths = None

def init():
	global paths

	try:
		path = os.environ['CHOICESPATH']
		paths = string.split(path, ':')
	except KeyError:
		paths = [ os.environ['HOME'] + '/Choices',
			  '/usr/local/share/Choices',
			  '/usr/share/Choices' ]
	
def load(dir, leaf):
	"Eg ('Edit', 'Options') - > '/usr/local/share/Choices/Edit/Options'"

	if paths == None:
		init()

	for path in paths:
		full = path + '/' + dir + '/' + leaf
		if exists(full):
			return full

	return None
