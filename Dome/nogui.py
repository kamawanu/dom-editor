#!/usr/bin/env python

import findrox

no_gui_mode = 1

from Beep import Beep

#import gc
#gc.set_debug(gc.DEBUG_LEAK)

try:
	import rox
except:
	print "(no GUI, but that's OK)"

from rox import choices, support

def error(message, title = 'Error'):
	print "*********", title
	print message, "\n"
support.report_error = error

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

if len(sys.argv) < 2:
	print "Usage: python nogui.py [--profile] [--xmlonly] <document>"
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
model = Model(source, dome_data = xml_data)

view = View(model, callback_handlers = (idle_add, idle_remove))

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

if profiling:
	import profile
	print "Profiling..."
	profile.run('run_nogui()')
else:
	run_nogui()

if view.chroots:
	raise Exception("Processing stopped in a chroot! -- not saving")

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
