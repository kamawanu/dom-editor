#!/usr/bin/env python

import sys
from xml.dom import ext

from Model import Model
from View import View, Done

model = Model()
view = View(model)

if len(sys.argv) < 2:
	print "Usage: python nogui.py <code> [DATA]..."
	sys.exit(0)

code = sys.argv[1]
model.load_program(code)

print "XXX: root_program!"
view.set_exec((model.root_program.start, 'next'))
try:
	while 1:
		view.do_one_step()
except Done:
	print "Done!"

ext.PrettyPrint(model.doc)
