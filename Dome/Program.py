from xml.parsers.xmlproc.utils import escape_attval
from xml.dom.ext.reader import PyExpat
import string

from support import *

def el_named(node, name):
	for n in node.childNodes:
		if n.localName == name:
			return n
	return None
	
# Node is a DOM <dome-program> or <node> node.
# Returns the start Op.
def load(chain):
	start = None
	prev = None
	for op_node in chain.childNodes:
		if str(op_node.localName) != 'node':
			continue
		
		attr = op_node.getAttributeNS('', 'action')
		action = eval(str(attr))
		if action[0] == 'chroot':
			action[0] = 'enter'
		elif action[0] == 'unchroot':
			action[0] = 'leave'
		#elif action[0] == 'set_attrib':
		#	if action[3] == '':
		#		action = ('add_attrib', action[1], action[2])
		#	else:
		#		action = ('set_attrib', action[3])
		elif action[0] == 'playback':
			action[0] = 'map'

		op = Op(action)

		if not start:
			start = op
		if prev:
			prev.link_to(op, 'next')
		prev = op
		
		fail = load(op_node)
		if fail:
			op.link_to(fail, 'fail')
	return start

def load_dome_program(model, prog):
	"prog should be a DOM 'dome-program' node."
	if prog.nodeName != 'dome-program':
		raise Exception('Not a DOME program!')

	new = Program(model, str(prog.getAttributeNS('', 'name')))

	start = load(prog)
	if start:
		new.set_start(start)

	print "Loading '%s'..." % new.name

	for node in prog.childNodes:
		if node.localName == 'dome-program':
			new.add_sub(load_dome_program(model, node))
		
	return new

class Program:
	"A program contains a Start Op and any number of sub-programs."
	def __init__(self, model, name, start = None):
		if not start:
			start = Op()
			start.program = self
		self.model = model
		self.start = start
		self.name = name
		self.subprograms = {}
		self.watchers = []
		self.parent = None
	
	def set_start(self, start):
		start.set_program(self)
		self.start = start
		self.changed(None)

	def changed(self, op):
		for w in self.watchers:
			w.program_changed(self)
	
	def add_sub(self, prog):
		if prog.parent:
			raise Exception('%s already has a parent program!' % prog.name)
		if self.subprograms.has_key(prog.name):
			raise Exception('%s already has a child called %s!' %
							(self.name, prog.name))
		if prog.model != self.model:
			raise Exception('Subprogram is from a different model!')
		prog.parent = self
		self.subprograms[prog.name] = prog
		self.model.prog_tree_changed(prog)
	
	def remove_sub(self, prog):
		if prog.parent != self:
			raise Exception('%s is no child of mime!' % prog)
		prog.parent = None
		del self.subprograms[prog.name]
		self.model.prog_tree_changed(self)
	
	def rename(self, name):
		p = self.parent
		if p.subprograms.has_key(name):
			raise Exception('%s already has a child called %s!' % (p.name, name))
		p.remove_sub(self)
		self.name = name
		p.add_sub(self)
	
	def to_xml(self):
		data = "<dome-program name='%s'>\n" % escape_attval(self.name)
	
		data += self.start.to_xml_int()

		for p in self.subprograms.values():
			data += p.to_xml()

		return data + "</dome-program>\n"
	
class Op:
	"Each node in a chain is an Op. There is no graphical stuff in here."

	def __init__(self, action = None):
		"Creates a new node (can be linked into another node later)"
		if not action:
			action = ['Start']
		self.program = None
		self.action = action
		self.next = None
		self.fail = None
		self.prev = None
	
	def set_program(self, program):
		if self.program:
			raise Exception('%s already has a program!' % start)
	 	self.program = program
		if self.next:
			self.next.set_program(program)
		if self.fail:
			self.fail.set_program(program)
	
	def changed(self):
		if self.program:
			self.program.changed(self)
	
	def swap_nf(self):
		(self.next, self.fail) = (self.fail, self.next)
		self.changed()
	
	def link_to(self, child, exit):
		# Create a link from this exit to this child Op
		if child.prev or child.program:
			raise Exception('%s is already in a chain!' % child)
		current = getattr(self, exit)
		if current:
			if child.next:
				raise Exception('%s already has a next exit' % child)
			self.unlink(current)
			child.link_to(current, 'next')
		child.prev = self
		child.program = self.program
		setattr(self, exit, child)
		self.changed()
	
	def unlink(self, child):
		"child becomes a Start node"
		if child.prev != self:
			raise Exception('forget_child: not my child!')
		child.prev = None
		child.program = None

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
			self.unlink(next)

		prev = self.prev
		if prev.next == self:
			exit = 'next'
		else:
			exit = 'fail'
		prev.unlink(self)
		if next:
			prev.link_to(next, exit)

		self.prev = None
		self.next = None
		xml = self.to_xml()
		self.action = None
		self.fail = None
		self.program = None
		return xml
	
	def del_chain(self):
		xml = self.to_xml()
		self.prev.unlink(self)
		return xml
	
	def to_xml(self):
		return '<dome-program>\n' + self.to_xml_int() + '</dome-program>\n'
		
	def to_xml_int(self):
		"Returns a chain of <Node> elements. So, if you want XML, enclose it "
		"in something."
		next = self.next
		fail = self.fail
		act = escape_attval(`self.action`)
		ret = '<node action="%s"' % act
		if fail == None:
			ret += '/>\n'
		else:
			ret += '>\n' + self.fail.to_xml_int() + '</node>'

		if self.next:
			ret += self.next.to_xml_int()
		return ret
	
	def __str__(self):
		return "{" + `self.action` + "}"

