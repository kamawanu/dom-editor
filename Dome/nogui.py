#!/usr/bin/env python

import findrox
from Beep import Beep

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
from xml.dom import ext
from xml.dom.ext.reader import PyExpat

from Model import Model
from View import View, Done, InProgress
from Program import Program, load_dome_program

if len(sys.argv) < 2:
	print "Usage: python nogui.py <document>"
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
model = Model(source)

view = View(model, callback_handlers = (idle_add, idle_remove))

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

if view.chroots:
	raise Exception("Processing stopped in a chroot! -- not saving")

import shutil

shutil.copyfile(source, source + '.bak')

doc = view.export_all()
ext.PrettyPrint(doc, stream = open(source, 'w'))

if source[-5:] == '.dome':
	xml = source[:-5] + '.xml'
else:
	xml = source + '.xml'
ext.PrettyPrint(view.model.doc, stream = open(xml, 'w'))
