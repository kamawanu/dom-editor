from xml.parsers.xmlproc.utils import escape_attval
from xml.dom.ext.reader import PyExpat
from StringIO import StringIO
import string

from support import *

def el_named(node, name):
	for n in node.childNodes:
		if n.localName == name:
			return n
	return None
	
def load_xml(op_xml):
	reader = PyExpat.Reader()
	doc = reader.fromStream(StringIO(op_xml))
	return load(doc.documentElement)

# Node is a DOM node: <node action="...">[<fail>][<node>]</node>.
# Returns the start Op.
def load(program, node):
	attr = node.getAttributeNS('', 'action')
	action = eval(str(attr))
	if action[0] == 'chroot':
		action[0] = 'enter'
	elif action[0] == 'unchroot':
		action[0] = 'leave'
	elif action[0] == 'playback':
		action[0] = 'map'

	op = Op(program, action)
		
	next = el_named(node, 'node')
	fail = el_named(node, 'fail')

	if next:
		op.link_to(load(program, next), 'next')
	if fail:
		op.link_to(load(program, fail), 'fail')
	
	return op

def load_dome_program(prog):
	"prog should be a DOM 'dome-program' node."
	if prog.nodeName != 'dome-program':
		raise Exception('Not a DOME program!')

	new = Program(str(prog.getAttributeNS('', 'name')))

	node = el_named(prog, 'node')
	if node:
		new.set_start(load(new, node))

	print "Loading '%s'..." % new.name

	for node in prog.getElementsByTagNameNS('', 'dome-program'):
		new.add_sub(load_dome_program(node))
		
	return new

class Program:
	"A program contains a Start Op and any number of sub-programs."
	def __init__(self, name, start = None):
		if not start:
			start = Op(self)
		self.start = start
		self.name = name
		self.subprograms = []
		self.watchers = []
	
	def set_start(self, start):
		self.start = start
		self.changed(None)

	def changed(self, op):
		if op:
			print "%s: Op(%s) changed." % (self.name, op.action)
		else:	
			print "%s: Changed" % self.name
		for w in self.watchers:
			w(self)
	
	def add_sub(self, prog):
		self.subprograms.append(prog)
		self.changed(None)
	
class Op:
	"Each node in a chain is an Op. There is no graphical stuff in here."

	def __init__(self, program, action = None):
		"Creates a new node (can be linked into another node later)"
		if not action:
			action = ['Start']
		if not isinstance(program, Program):
			raise Exception('Not a program!')
		self.program = program
		self.action = action
		self.next = None
		self.fail = None
		self.prev = None
	
	def changed(self):
		self.program.changed(self)
	
	def link_to(self, child, exit):
		# Create a link from this exit to this child Op
		if getattr(self, exit) != None:
			raise Exception('%s already has a %s child op!' % (self, exit))
		setattr(self, exit, child)
		self.changed()
	
	def unlink(self, child):
		"child becomes a Start node"
		if child.prev != self:
			raise Exception('forget_child: not my child!')
		child.prev = None

		if child == self.next:
			exit = 'next'
		else:
			exit = 'fail'
		setattr(self, exit, None)

		self.changed()

	def swap_nf(self):
		self.next, self.fail = (self.fail, self.next)
		self.changed()
	
	def del_node(self):
		"Remove this node, linking our next and previous nodes."
		"Error if we have fail and next nodes..., or if we have no prev node"
		if self.next and self.fail:
			raise Exception("Can't delete a node with both fail and next exits in use.")
		if not self.prev:
			raise Exception("Can't delete a Start node!")

		if self.next:
			next = self.next
		else:
			next = self.fail

		if next:
			next.prev = None

		prev = self.prev
		if prev.next == self:
			exit = 'next'
		else:
			exit = 'fail'
		prev.link_to(next, exit)

		self.action = None
		self.prev = None
		self.next = None
		self.fail = None
		self.program = None
	
	def del_chain(self):
		xml = self.to_xml()
		self.prev.unlink(self)
		return xml
	
	def to_xml(self):
		next = self.next
		fail = self.fail
		act = escape_attval(`self.action`)
		ret = '<node action="%s"' % act
		if next == None and fail == None:
			return ret + '/>\n'
		ret += '>\n'

		if fail:
			ret += '<fail>\n' + fail.add() + '</fail>'

		if next:
			return ret + next.add() + '</node>'
		return ret + '</node>'
	
	def __str__(self):
		return "{" + `self.action` + "}"

