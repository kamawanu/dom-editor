from __future__ import nested_scopes
import string
from constants import DOME_NS
from xml.dom import Node

def el_named(node, name):
	for n in node.childNodes:
		if n.localName == name:
			return n
	return None
	
# Converts a DOM <block> node to a Block object.
def load(node, parent):
	#assert node.localName == 'block'

	block = Block(parent)
	try:
		if int(node.getAttributeNS(None, 'foreach')):
			block.toggle_foreach()
		if int(node.getAttributeNS(None, 'enter')):
			block.toggle_enter()
		prev = block.start
	except:
		pass

	id_hash = {}		# id from file -> Op
	to_link = []
	def _load(chain, prev, exit):
		for op_node in chain.childNodes:
			if str(op_node.localName) == 'node':
				attr = op_node.getAttributeNS(None, 'action')
				action = eval(str(attr))
				if action[0] == 'Start':
					print "Skipping Start"
					continue
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
				elif action[0] == 'add_attrib':
					action[1] = "UNUSED"
				op = Op(action)
			elif op_node.localName == 'block':
				op = load(op_node, block)
			else:
				if op_node.nodeType == Node.ELEMENT_NODE:
					print "** WARNING ** Unknown op:", op_node
				continue

			try:
				dx = int(float(op_node.getAttributeNS(None, 'dx')))
				if dx:
					op.dx = dx
				dy = int(float(op_node.getAttributeNS(None, 'dy')))
				if dy:
					op.dy = dy
			except:
				pass

			node_id = op_node.getAttributeNS(None, 'id')
			if node_id:
				id_hash[node_id] = op

			prev.link_to(op, exit)
			exit = 'next'
			prev = op
			
			if op_node.nodeName == 'block':
				# Block nodes have a special failure child
				for x in op_node.childNodes:
					if x.localName == 'fail':
						_load(x, op, 'fail')
						break
			else:
				# If the new node has children then they are the failure case
				_load(op_node, op, 'fail')

			link = op_node.getAttributeNS(None, 'target_fail')
			if link:
				to_link.append((op, 'fail', link))
			link = op_node.getAttributeNS(None, 'target_next')
			if link:
				to_link.append((op, 'next', link))
	_load(node, block.start, 'next')
	for (op, exit, child) in to_link:
		try:
			to = id_hash[child]
		except:
			print "**** Not adding link to unknown ID ****"
		else:
			op.link_to(to, exit)
	return block

def load_dome_program(prog):
	"prog should be a DOM 'dome-program' node."
	#print "Loading", prog
	if prog.localName != 'dome-program':
		raise Exception('Not a DOME program: %s!' % prog)

	new = Program(str(prog.getAttributeNS(None, 'name')))

	#print "Loading '%s'..." % new.name
	done_update = 0

	for node in prog.childNodes:
		if node.localName == 'node' and not done_update:
			print "*** Converting from old format ***"
			new.code = load(prog, new)
			done_update = 1
		if node.localName == 'block':
			assert not done_update
			new.code = load(node, new)
		if node.localName == 'dome-program':
			new.add_sub(load_dome_program(node))
		
	return new

class Program:
	"A program contains a code Block and any number of sub-programs."
	def __init__(self, name):
		assert '/' not in name

		self.code = Block(self)
		
		self.name = name
		self.subprograms = {}
		self.watchers = []
		self.parent = None

	def get_path(self):
		path = ""
		p = self
		while p:
			path = p.name + '/' + path
			p = p.parent
		return path[:-1]
	
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
		
		node.appendChild(self.code.to_xml(doc))

		# Keep them in the same order to help with diffs...
		progs = self.subprograms.keys()
		progs.sort()

		for name in progs:
			p = self.subprograms[name]
			node.appendChild(p.to_xml(doc))

		return node
	
	def __str__(self):
		return "Program(%s)" % self.name

class Op:
	"Each node in a chain is an Op. There is no graphical stuff in here."

	def __init__(self, action = None):
		"Creates a new node (can be linked into another node later)"
		if not action:
			action = ['Start']
		self.parent = None
		self.action = action
		self.next = None
		self.fail = None
		self.prev = []		# First parent is used for rendering as a tree
		self.dx, self.dy = (0, 0)
	
	def set_parent(self, parent):
		if self.parent == parent:
			return
		if parent and self.parent:
			raise Exception('Already got a parent!')
		nearby = self.prev[:]
		if self.next:
			nearby.append(self.next)
		if self.fail:
			nearby.append(self.fail)
		self.parent = parent
		[x.set_parent(parent) for x in nearby if x.parent is not parent]
	
	def changed(self, op = None):
		self.parent.changed(op or self)
	
	def swap_nf(self):
		assert self.action[0] != 'Start'
		self.next, self.fail = (self.fail, self.next)
		self.changed()
	
	def link_to(self, child, exit):
		# Create a link from this exit to this child Op
		assert self.action[0] != 'Start' or exit == 'next'
		assert child.action[0] != 'Start'

		print "Link %s:%s -> %s" % (self, exit, child)
		
		if child.parent and child.parent is not self.parent:
			raise Exception('%s is from a different parent (%s vs %s)!' %
					(child, child.parent, self.parent))
		# If we already have something on this exit, and the new node has a
		# clear next exit, move the rest of the chain there.
		child.set_parent(self.parent)
		current = getattr(self, exit)
		if current:
			if child.next:
				raise Exception('%s already has a next exit' % child)
			self.unlink(exit, may_delete = 0)
			child.link_to(current, 'next')
		child.prev.append(self)
		setattr(self, exit, child)
		self.changed()
	
	def unlink(self, exit, may_delete = 1):
		"Remove link from us to child"
		assert exit in ['next', 'fail']
		self._unlink(exit, may_delete)
		self.changed()
	
	def _unlink(self, exit, may_delete = 1):
		child = getattr(self, exit)
		if not child:
			raise Exception('%s has no child on exit %s' % (self, exit))
		if self not in child.prev:
			raise Exception('Internal error: %s not my child!' % child)

		child.prev.remove(self)	# Only remove one copy
		setattr(self, exit, None)

		for x in child.prev: print x

		if may_delete and not child.prev:
			# There is no way to reach this child now, so unlink its children.
			child.parent = None
			if child.next:
				child._unlink('next')
			if child.fail:
				child._unlink('fail')

	def del_node(self):
		"""Remove this node. It there is exactly one out-going arc and one incoming one,
		join them together. Error if:"
		- There are multiple out-going arcs
		- There is a single out-going arc but multiple parents"""
		if self.next and self.fail:
			raise Exception("Can't delete a node with both fail and next exits in use.")
		if not self.prev:
			raise Exception("Can't delete a Start node!")

		prog = self.parent

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
			self.unlink(exit, may_delete = 0)

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
		self.parent = None

		prog.changed()
		return doc
	
	def to_doc(self):
		from xml.dom import implementation
		doc = implementation.createDocument(DOME_NS, 'dome-program', None)
		self.to_xml_int(doc.documentElement)
		return doc
	
	def to_xml(self, doc):
		node = doc.createElementNS(DOME_NS, 'node')
		node.setAttributeNS(None, 'action', `self.action`)
		node.setAttributeNS(None, 'dx', str(self.dx))
		node.setAttributeNS(None, 'dy', str(self.dy))
		return node
	
	def to_xml_int(self, parent):
		"""Adds a chain of <Node> elements to 'parent'. Links only followed when node is
		first parent."""
		node = self.to_xml(parent.ownerDocument)
		parent.appendChild(node)

		if len(self.prev) > 1:
			node.setAttributeNS(None, 'id', str(id(self)))

		def add_link(op, parent):
			node = parent.ownerDocument.createElementNS(DOME_NS, 'link')
			parent.appendChild(node)
			node.setAttributeNS(None, 'target', str(id(op)))

		if self.fail:
			if self.fail.prev[0] == self:
				if isinstance(self, Block):
					fail = parent.ownerDocument.createElementNS(DOME_NS, 'fail')
					self.fail.to_xml_int(fail)
					node.appendChild(fail)
				else:
					self.fail.to_xml_int(node)
			else:
				node.setAttributeNS(None, 'target_fail', str(id(self.fail)))
		if self.next:
			if self.next.prev[0] == self:
				self.next.to_xml_int(parent)
			else:
				node.setAttributeNS(None, 'target_next', str(id(self.next)))
	
	def __str__(self):
		return "{" + `self.action` + "}"
	
	def get_program(self):
		p = self.parent
		while not isinstance(p, Program):
			p = p.parent
		return p

class Block(Op):
	"""A Block is an Op which contains a group of Ops."""

	def __init__(self, parent):
		Op.__init__(self, action = ['Block'])
		self.parent = parent
		self.start = Op()
		self.start.parent = self
		self.foreach = 0
		self.enter = 0
	
	def set_start(self, start):
		assert not start.prev

		start.set_parent(self)
		self.start = start
		self.changed()

	def is_toplevel(self):
		return not isinstance(self.parent, Block)

	def link_to(self, child, exit):
		assert not self.is_toplevel()
		Op.link_to(self, child, exit)
	
	def to_xml(self, doc):
		node = doc.createElementNS(DOME_NS, 'block')
		node.setAttributeNS(None, 'foreach', str(self.foreach))
		node.setAttributeNS(None, 'enter', str(self.enter))
		assert not self.start.fail
		if self.start.next:
			self.start.next.to_xml_int(node)
		return node
	
	def toggle_enter(self):
		self.enter = not self.enter
		self.changed()
	
	def toggle_foreach(self):
		self.foreach = not self.foreach
		self.changed()
