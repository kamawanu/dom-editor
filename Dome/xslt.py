from constants import XSLT_NS
from xml.dom import Node

# Plan:

# Root program is the template-dispatcher which checks to see if the current node
# matches a series of patterns (in priority order) and calls the appropriate program
# for the template.

from Ft.Xml.Xslt.StylesheetReader import StylesheetReader
from Ft.Xml.Xslt.StylesheetTree import XsltElement, XsltText
from Ft.Xml.Xslt.LiteralElement import LiteralElement
from Ft.Xml.Xslt.ApplyTemplatesElement import ApplyTemplatesElement
from Program import Program, Op, Block

def import_sheet(doc):
	print "Import!", doc

	root = Program('XSLT')

	# To start with, the mark is on the source document node and
	# the cursor is on the result document node.
	#
	# The root program is called with:
	# => Cursor = context node
	#    Mark = result parent (append here)
	# <= Cursor is undefined
	#    Mark is unchanged
	op = add(root.code.start, 'do_search', '/xslt/Result')
	op = add(op, 'mark_selection')
	op = add(op, 'do_search', '/xslt/Source')
	op = add(op, 'play', 'XSLT/Default mode')
	
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
			mode_name = 'Mode:' + mode[1]
		else:
			mode_name = 'Default mode'
		prog = Program(mode_name)
		root.add_sub(prog)
		tests = prog.code.start
		print "Mode", mode
		types = sheet.matchTemplates[mode]
		loose_ends = []
		for type in types.keys():
			if type == Node.ELEMENT_NODE:
				templates = types[type].values()
			else:
				templates = [types[type]]
			for tl in templates:
				for t in tl:
					pattern = `t[0]`
					name = pattern.replace('/', '%')
					temp = Program(`i` + '-' + name)
					op = add(temp.code.start, 'mark_switch')
					make_template(op, t[2])
					i += 1
					prog.add_sub(temp)
					
					if pattern.startswith('/'):
						if pattern == '/':
							pattern = ''
						pattern = '/xslt/Source' + pattern # XXX: Hack
					tests = add(tests, 'fail_if', pattern)
					op = Op(action = ['play', temp.get_path()])
					tests.link_to(op, 'fail')
					loose_ends.append(op)
		# Now add the built-in rules

		print "Tidy", loose_ends

		tests = add(tests, 'do_global', '*')
		tests = add(tests, 'map', prog.get_path())
		tests = add(tests, 'mark_switch')
		tests = add(tests, 'mark_switch')
		[ op.link_to(tests, 'next') for op in loose_ends ]


	return root

def add(op, *action):
	new = Op(action = action)
	op.link_to(new, 'next')
	return new

# A template is instantiated by running its program.
#
# => Cursor = result parent (append here)
#    Mark = context node
#
# <= Cursor is undefined
#    Mark is unchanged
#
# Add the instructions to instantiate this template to 'op'.
def make_template(op, temp):
	op = add(op, 'mark_switch')
	block = Block(op.parent)
	block.toggle_restore()
	op.link_to(block, 'next')
	op = block.start
	op2 = add(block, 'mark_switch')

	op = add(op, 'mark_switch')
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
		elif isinstance(child, ApplyTemplatesElement):
			op = add(op, 'mark_switch')
			op = add(op, 'do_global', '*')	# XXX
			op = add(op, 'map', 'XSLT/Default mode')
			op = add(op, 'mark_switch')
		else:
			print "Unknown template type", child, "(%s)" % child.__class__
	op = add(op, 'mark_switch')

	return op2
