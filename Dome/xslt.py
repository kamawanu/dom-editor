from constants import XSLT_NS
from xml.dom import Node

# Plan:

# Root program is the template-dispatcher which checks to see if the current node
# matches a series of patterns (in priority order) and calls the appropriate program
# for the template.

from Ft.Xml.Xslt.StylesheetReader import StylesheetReader
from Ft.Xml.Xslt.StylesheetTree import XsltElement, XsltText
from Program import Program, Op

def import_sheet(doc):
	print "Import!", doc

	root = Program('XSLT')

	# To start with, the cursor is on the source document node and
	# the mark is on the result document node.
	op = Op(['do_search', '/xslt/Result'])
	root.start.link_to(op, 'next')
	op2 = Op(['mark_selection'])
	op.link_to(op2, 'next')
	op3 = Op(['do_search', '/xslt/Source'])
	op2.link_to(op3, 'next')

	reader = StylesheetReader()
	sheet = reader.fromDocument(doc)

	global s
	s = sheet
	print sheet

	# sheet.matchTemplates is { mode -> { type -> { (ns, name) -> [match]     for elements
	#                         		      { 	      [match]     otherwise
	#
	# Each match is (pattern, axis_type, TemplateElement)
	#
	# The list of matches is sorted; use the first that matches. Multiple lookups
	# may be required (eg, lookup 'html' then None (for 'node()' and '*')).
	# Patterns like 'text()|comment()' are broken down into two match elements.

	# XXX: Could have two modes with the same name but different namespaces...

	i = 1

	for mode in sheet.matchTemplates.keys():
		if mode:
			prog = Program('Mode:' + mode[1])
		else:
			prog = Program('Default mode')
		root.add_sub(prog)
		print "Mode", mode
		types = sheet.matchTemplates[mode]
		for type in types.keys():
			if type == Node.ELEMENT_NODE:
				templates = types[type].values()
			else:
				templates = [types[type]]
			for tl in templates:
				for t in tl:
					temp = Program(`i` + '-' + `t[0]`)
					make_template(temp, t[2])
					i += 1
					prog.add_sub(temp)
					print "Template", type, t
	

	return root

def add(op, *action):
	new = Op(action = action)
	op.link_to(new, 'next')
	return new

# A template is instantiated by running its program.
#
# => Cursor = context node
#    Mark   = result parent (append children here)
#
# <= Cursor is undefined
#    Mark is unchanged
def make_template(prog, temp):
	op = prog.start
	in_source = 1	# Where the cursor is
	for child in temp.children:
		if isinstance(child, XsltText):
			print "Text node", child.data
			op = add(op, 'mark_switch')
			op = add(op, 'add_node', 'et', child.data)
			op = add(op, 'move_left')
			op = add(op, 'mark_switch')

		else:
			print "Unknown template type", child, "(%s)" % child.__class__
