from constants import XSLT_NS
from xml.dom import Node

# Plan:

# Root program is the template-dispatcher which checks to see if the current node
# matches a series of patterns (in priority order) and calls the appropriate program
# for the template.

from Ft.Xml.Xslt.StylesheetReader import StylesheetReader
from Ft.Xml.Xslt.StylesheetTree import XsltElement, XsltText
from Ft.Xml.Xslt.LiteralElement import LiteralElement
from Program import Program, Op

def import_sheet(doc):
	print "Import!", doc

	root = Program('XSLT')

	# To start with, the mark is on the source document node and
	# the cursor is on the result document node.
	op = Op(['do_search', '/xslt/Source'])
	root.start.link_to(op, 'next')
	op2 = Op(['mark_selection'])
	op.link_to(op2, 'next')
	op3 = Op(['do_search', '/xslt/Result'])
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
					name = `t[0]`.replace('/', '%')
					temp = Program(`i` + '-' + name)
					make_template(temp.start, t[2])
					i += 1
					prog.add_sub(temp)
	

	return root

def add(op, *action):
	new = Op(action = action)
	op.link_to(new, 'next')
	return new

# A template is instantiated by running its program.
#
# => Mark   = context node
#    Cursor = result parent (append children here)
#
# <= Cursor is unchanged
#    Mark is undefined
#
# Add the instructions to instantiate this template to 'op'.
def make_template(op, temp):
	for child in temp.children:
		if isinstance(child, XsltText):
			print "Text node", child.data
			op = add(op, 'add_node', 'et', child.data)
			op = add(op, 'move_left')

		elif isinstance(child, LiteralElement):
			print "Element", child._output_qname
			op = add(op, 'add_node', 'ee', child._output_qname)
			op = make_template(op, child)
			op = add(op, 'move_left')
		else:
			pass
			#print "Unknown template type", child, "(%s)" % child.__class__
	return op
