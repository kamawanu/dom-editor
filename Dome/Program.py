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

		try:
			dx = int(float(op_node.getAttributeNS(None, 'dx')))
			if dx:
				op.dx = dx
			dy = int(float(op_node.getAttributeNS(None, 'dy')))
			if dy:
				op.dy = dy
		except:
			pass

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
	#print "Loading", prog
	if prog.nodeName != 'dome-program':
		raise Exception('Not a DOME program!')

	new = Program(str(prog.getAttributeNS(None, 'name')))

	start = load(prog)
	if start:
		new.set_start(start)

	#print "Loading '%s'..." % new.name

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
		if self.parent:
			self.parent.changed(op)
		else:
			for w in self.watchers:
				w.program_changed(op)
	
	def tree_changed(self):
		if self.parent:
			self.parent.tree_changed()
		else:
			for w in self.watchers:
				w.prog_tree_changed()
	
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
		self.prev = []		# First parent is used for rendering as a tree
		self.dx, self.dy = (0, 0)
	
	def set_program(self, program):
		if self.program == program:
			return
		if self.program:
			raise Exception('Already got a program!')
		nearby = self.prev
		if self.next:
			nearby.append(self.next)
		if self.fail:
			nearby.append(self.fail)
		self.program = program
		print nearby
		[x.set_program(program) for x in nearby if x.program is not program]
	
	def changed(self):
		if self.program:
			self.program.changed(self)
	
	def swap_nf(self):
		self.next, self.fail = (self.fail, self.next)
		self.changed()
	
	def link_to(self, child, exit):
		# Create a link from this exit to this child Op
		if child.program and child.program is not self.program:
			raise Exception('%s is from a different program!' % child)
		# If we already have something on this exit, and the new node has a
		# clear next exit, move the rest of the chain there.
		current = getattr(self, exit)
		if current:
			if child.next:
				raise Exception('%s already has a next exit' % child)
			self.unlink(exit)
			child.link_to(current, 'next')
		child.prev.append(self)
		child.set_program(self.program)
		setattr(self, exit, child)
		self.changed()
	
	def unlink(self, exit):
		"Remove link from us to child"
		assert exit in ['next', 'fail']
		child = getattr(self, exit)
		if not child:
			raise Exception('%s has no child on exit %s' % (self, exit))
		if self not in child.prev:
			raise Exception('Internal error: %s not my child!' % child)

		child.prev.remove(self)	# Only remove one copy
		if not child.prev:
			child.program = None

		setattr(self, exit, None)

		self.changed()

	def del_node(self):
		"""Remove this node. It there is exactly one out-going arc and one incoming one,
		join them together. Error if:"
		- There are multiple out-going arcs
		- There is a single out-going arc but multiple parents"""
		if self.next and self.fail:
			raise Exception("Can't delete a node with both fail and next exits in use.")
		if not self.prev:
			raise Exception("Can't delete a Start node!")

		prog = self.program

		# Find the chain to preserve (can't have both set here)
		if self.next:
			exit = 'next'
		elif self.fail:
			exit = 'fail'
		else:
			exit = None
			
		if exit:
			if len(self.prev) != 1:
				raise Exception("Deleted node-chain must have a single link in")
			prev = self.prev[0]
			preserve = getattr(self, exit)
			self.unlink(exit)

		# Remove all links to us
		for p in self.prev:
			if p.next == self:
				p.unlink('next')
			if p.fail == self:
				p.unlink('fail')

		if exit:
			# Relink following nodes to our (single) parent
			prev.link_to(preserve, exit)

		assert not self.prev
		assert not self.next
		assert not self.fail
		doc = self.to_doc()
		self.action = None
		self.program = None

		prog.changed()
		return doc
	
	def to_doc(self):
		from xml.dom import implementation
		doc = implementation.createDocument(DOME_NS, 'dome-program', None)
		self.to_xml_int(doc.documentElement)
		return doc
	
	def to_xml_int(self, parent):
		"""Adds a chain of <Node> elements to 'parent'. Links only followed when node is
		first parent."""
		node = parent.ownerDocument.createElementNS(DOME_NS, 'node')
		parent.appendChild(node)
		node.setAttributeNS(None, 'action', `self.action`)
		node.setAttributeNS(None, 'dx', str(self.dx))
		node.setAttributeNS(None, 'dy', str(self.dy))
		
		if self.fail and self.fail.prev[0] == self:
			self.fail.to_xml_int(node)
		if self.next and self.next.prev[0] == self:
			self.next.to_xml_int(parent)
	
	def __str__(self):
		return "{" + `self.action` + "}"

