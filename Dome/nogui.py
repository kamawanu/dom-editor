#!/usr/bin/env python

import findrox

try:
	import rox
except:
	print "(no GUI, but that's OK)"

from rox import choices

import sys
from xml.dom import ext
from xml.dom.ext.reader import PyExpat

from Model import Model
from View import View, Done, InProgress
from Program import Program, load_dome_program

if len(sys.argv) < 2:
	print "Usage: python nogui.py <code> [<document>]"
	sys.exit(0)

code = choices.load('Dome', 'RootProgram.xml')
if code:
	reader = PyExpat.Reader()
	doc = reader.fromUri(code)
	root_program = load_dome_program(doc.documentElement)
else:
	root_program = Program('Root')

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

model = Model('Document')
view = View(model, root_program, callback_handlers = (idle_add, idle_remove))

code = sys.argv[1]

if len(sys.argv) > 2:
	source = sys.argv[2]
	view.load_xml(source)

print "Starting program", sys.argv[1]

view.run_new(None)

try:
	view.may_record(['play', sys.argv[1]])
except InProgress:
	pass

while idle_list:
	for i in idle_list[:]:
		if not i.fn():
			idle_remove(i)

print "Done!"

import shutil

shutil.copyfile(source, source + '.bak')

ext.PrettyPrint(model.doc, stream = open(source, 'w'))
