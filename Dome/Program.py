import string
from constants import DOME_NS

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
		
		attr = op_node.getAttributeNS(None, 'action')
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
		elif action[0] == 'add_attrib' or action[0] == 'attribute':
			if action[1] == '':
				action[1] = None

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

def load_dome_program(prog):
	"prog should be a DOM 'dome-program' node."
	if prog.nodeName != 'dome-program':
		raise Exception('Not a DOME program!')

	new = Program(str(prog.getAttributeNS(None, 'name')))

	start = load(prog)
	if start:
		new.set_start(start)

	print "Loading '%s'..." % new.name

	for node in prog.childNodes:
		if node.localName == 'dome-program':
			new.add_sub(load_dome_program(node))
		
	return new

class Program:
	"A program contains a Start Op and any number of sub-programs."
	def __init__(self, name, start = None):
		if not start:
			start = Op()
			start.program = self
		self.start = start
		self.name = name
		self.subprograms = {}
		self.watchers = []
		self.parent = None
	
	def set_start(self, start):
		start.set_program(self)
		self.start = start
		self.changed(None)

	def changed(self, op = None):
		for w in self.watchers:
			w.program_changed(self)
	
	def tree_changed(self):
		if self.parent:
			self.parent.tree_changed()
		else:
			for w in self.watchers:
				w.prog_tree_changed(self)
	
	def add_sub(self, prog):
		if prog.parent:
			raise Exception('%s already has a parent program!' % prog.name)
		if self.subprograms.has_key(prog.name):
			raise Exception('%s already has a child called %s!' %
							(self.name, prog.name))
		prog.parent = self
		self.subprograms[prog.name] = prog
		self.tree_changed()
	
	def remove_sub(self, prog):
		if prog.parent != self:
			raise Exception('%s is no child of mime!' % prog)
		prog.parent = None
		del self.subprograms[prog.name]
		self.tree_changed()
	
	def rename(self, name):
		p = self.parent
		if p:
			if p.subprograms.has_key(name):
				raise Exception('%s already has a child called %s!' % (p.name, name))
			p.remove_sub(self)
		self.name = name
		if p:
			p.add_sub(self)
		else:
			self.tree_changed()
	
	def to_xml(self, doc):
		node = doc.createElementNS(DOME_NS, 'dome-program')
		node.setAttributeNS(None, 'name', self.name)
		
		self.start.to_xml_int(node)

		for p in self.subprograms.values():
			node.appendChild(p.to_xml(doc))

		return node
	
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
		child.set_program(self.program)
		setattr(self, exit, child)
		self.changed()
	
	def set_program(self, program):
		if self.program == program:
			return
		if self.program:
			raise Exception('Already got a program!')
		self.program = program
		if self.next:
			self.next.set_program(program)
		if self.fail:
			self.fail.set_program(program)
	
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

		prog = self.program

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
		doc = self.to_doc()
		self.action = None
		self.fail = None
		self.program = None

		prog.changed()
		return doc
	
	def del_chain(self):
		doc = self.to_doc()
		self.prev.unlink(self)
		return doc

	def to_doc(self):
		from xml.dom import implementation
		doc = implementation.createDocument(DOME_NS, 'dome-program', None)
		self.to_xml_int(doc.documentElement)
		return doc
	
	def to_xml_int(self, parent):
		"Adds a chain of <Node> elements to 'parent'."
		node = parent.ownerDocument.createElementNS(DOME_NS, 'node')
		parent.appendChild(node)
		node.setAttributeNS(None, 'action', `self.action`)
		
		if self.fail:
			self.fail.to_xml_int(node)
		if self.next:
			self.next.to_xml_int(parent)
	
	def __str__(self):
		return "{" + `self.action` + "}"

