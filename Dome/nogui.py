#!/usr/bin/env python

import findrox
from rox import choices

import sys
from xml.dom import ext
from xml.dom.ext.reader import PyExpat

from Model import Model
from View import View, Done
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

model = Model('Document')
view = View(model, root_program)

code = sys.argv[1]

if len(sys.argv) > 2:
	view.load_xml(sys.argv[2])

print "Starting program", sys.argv[1]

idle_cb = []
try:
	view.may_record(['play', sys.argv[1]])
except InProgress:
	pass

while idle_cb:
	for i in idle_cb:
		i()

print "Done!"

#ext.PrettyPrint(model.doc)
