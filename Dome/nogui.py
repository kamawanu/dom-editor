#!/usr/bin/env python

import findrox

no_gui_mode = 1

from Beep import Beep

import gc
#gc.set_debug(gc.DEBUG_LEAK)

try:
	import rox
except:
	print "(no GUI, but that's OK)"

import rox
from rox import choices

def error(message, title = 'Error'):
	print "*********", title
	print message, "\n"
rox.report_error = error
def exc(): raise
rox.report_exception = exc

import sys
#from xml.dom import ext
from Ft.Xml.Domlette import PrettyPrint

from Model import Model
from View import View, Done, InProgress
from Program import Program, load_dome_program

if len(sys.argv) > 1 and sys.argv[1] == '--profile':
	profiling = 1
	del sys.argv[1]
else:
	profiling = 0

if len(sys.argv) > 1 and sys.argv[1] == '--xmlonly':
	xmlonly = 1
	del sys.argv[1]
else:
	xmlonly = 0

if len(sys.argv) > 1 and sys.argv[1] == '--leaks':
	show_leaks = True
	del sys.argv[1]
else:
	show_leaks = False

if len(sys.argv) < 2:
	print "Usage: python nogui.py [--profile] [--xmlonly] [--leaks] <document>"
	sys.exit(0)

idle_list = []

class Callback:
	def __init__(self, fn):
		self.fn = fn

def idle_add(function):
	new = Callback(function)
	idle_list.append(new)
	return new

def idle_remove(tag):
	try:
		idle_list.remove(tag)
	except ValueError:
		pass

source = sys.argv[1]
if len(sys.argv) > 2:
	xml_data = sys.argv[2]
else:
	xml_data = None

def run_nogui():
	print "Starting root program of", source

	view.run_new(None)

	try:
		view.do_action(['play', model.root_program.name])
	except InProgress:
		pass
	except Beep:
		print "*** BEEP ***"
		raise

	while idle_list:
		for i in idle_list[:]:
			if not i.fn():
				idle_remove(i)

	print "Done!"

if show_leaks:
	`[]`	# Load repr stuff
	gc.collect()
	old = {}
	for x in gc.get_objects():
		old[id(x)] = None

model = Model(source, dome_data = xml_data)
view = View(model, callback_handlers = (idle_add, idle_remove))

if profiling:
	import profile
	print "Profiling..."
	profile.run('run_nogui()')
else:
	run_nogui()

if show_leaks:
	del view, model, idle_list
	gc.collect()
	for x in gc.get_objects():
		if id(x) not in old:
			print "New", type(x)
			print `x`[:80]
			for y in gc.get_referrers(x):
				if id(y) in old and y is not globals():
					print "\t%s" % `y`[:60]
	sys.exit(0)

if view.chroots:
	raise Exception("Processing stopped in a chroot! -- not saving")

view.model.strip_space()

import shutil

if not xmlonly:
	shutil.copyfile(source, source + '.bak')
	doc = view.export_all()
	PrettyPrint(doc, stream = open(source, 'w'))

if xml_data:
	output = xml_data
else:
	if source[-5:] == '.dome':
		output = source[:-5] + '.xml'
	else:
		output = source + '.xml'
PrettyPrint(view.model.doc, stream = open(output + '.new', 'w'))

import os
os.rename(output + '.new', output)
