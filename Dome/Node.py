import string

# Undo
#
# Each node contains undo and redo lists.
# Each list element contains the 'time' of the operation and enough
# information to reverse it.
# 'time' is a global variable that is incremented on every tree op.

op_time = 0

class NotANode(Exception):
	def __str__(self):
		return "Not a valid Node object"

class Reparent(Exception):
	def __str__(self):
		return "Node already has a parent node"

class Barren(Exception):
	def __str__(self):
		return "DataNode node can't have children"

class Loop(Exception):
	def __str__(self):
		return "Adding node would create a loop"

# Remove the namespace part
def strip_ns(name):
	i = string.find(name, ' ')
	if i != -1:
		return name[i + 1:]
	return name

class Node:
	def __init__(self, type, attribs = None):
		if attribs == None:
			self.attribs = {}
		else:
			self.attribs = attribs
		self.type = type
		self.kids = []
		self.undo = []
		self.redo = []
		self.undoing = 0
		self.redoing = 0
		self.parent = None
	
	def copy(self):
		new = Node(self.type)
		new.attribs = self.attribs.copy()
		for k in self.kids:
			nk = k.copy()
			new.kids.append(nk)
			nk.parent = new
		return new
	
	def set_type(self, type):
		self.add_undo(lambda self, t = self.type: self.set_type(t))
		self.type = type
	
	# Number of lines without children
	def get_lines(self):
		return 1
	
	# Returns the lines of lines needed to display this node and
	# all its children.
	def count_lines(self):
		n = self.get_lines()
		for k in self.kids:
			n = n + k.count_lines()
		return n
	
	# Set at most one of before, after and index.
	def add(self, subnode, before = None, after = None, index = None,
			undo = 1):
		if not isinstance(subnode, Node):
			raise NotANode, subnode
		if subnode.parent != None:
			raise Reparent, subnode

		p = self
		while p:
			if p == subnode:
				raise Loop, subnode
			p = p.parent

		if before:
			index = self.kids.index(before)
		elif after:
			index = self.kids.index(after) + 1

		if index == None:
			index = len(self.kids)

		self.kids.insert(index, subnode)

		if undo:
			self.add_undo(lambda self, c = subnode: self.remove(c))

		subnode.parent = self
	
	def can_undo(self):
		return self.latest_undo().undo_time() > 0

	def can_redo(self):
		return self.latest_redo().redo_time() > 0
	
	# Time of last op, or 0 if can't undo
	def undo_time(self):
		if len(self.undo) == 0:
			return 0
		t, f = self.undo[-1]
		return t
	
	# Time of last undo op, or 0 if can't redo
	def redo_time(self):
		if len(self.redo) == 0:
			return 0
		t, f = self.redo[-1]
		return t
	
	# Find the node that has most recently updated its undo buffer
	def latest_undo(self):
		time = self.undo_time()
		best = self

		for k in self.kids:
			n = k.latest_undo()
			n_time = n.undo_time()
			if n_time > time:
				best = n
				time = n_time

		return best

	# Find the node that has most recently updated its redo buffer
	def latest_redo(self):
		time = self.redo_time()
		best = self

		for k in self.kids:
			n = k.latest_redo()
			n_time = n.redo_time()
			if n_time > time:
				best = n
				time = n_time

		return best

	def do_undo(self):
		node = self.latest_undo()

		time, fn = node.undo.pop()

		node.undoing = 1
		fn(node)
		node.undoing = 0
	
	def do_redo(self):
		node = self.latest_redo()

		time, fn = node.redo.pop()

		node.redoing = 1
		fn(node)
		node.redoing = 0
	
	def add_undo(self, callback):
		global op_time
		op_time = op_time + 1
		if self.undoing:
			self.redo.append((op_time, callback))
		else:
			self.undo.append((op_time, callback))
			if not self.redoing:
				self.redo = []
	
	def __str__(self):
		retval = strip_ns(self.type)
		for a in self.attribs.keys():
			retval = retval + \
				', %s="%s"' % (strip_ns(a), self.attribs[a])
		return retval
	
	def remove(self, child):
		i = self.kids.index(child)
		self.kids.remove(child)
		child.parent = None
		self.add_undo(lambda self, c = child, i = i:
					self.add(c, index = i))
	
	def prev_sibling(self):
		sibs = self.parent.kids
		i = sibs.index(self)
		if i > 0:
			return sibs[i - 1]
		return None

	def next_sibling(self):
		sibs = self.parent.kids
		i = sibs.index(self)
		if i + 1 < len(sibs):
			return sibs[i + 1]
		return None

# Cannot have children.
# In:
# 	<note>Text<p/>More Text</note>
# the tree is:
# Node(note)
#   |--DataNode
#   |--Node(p/)
#   \--DataNode
class DataNode(Node):
	def __init__(self, text):
		Node.__init__(self, None)
		self.text = string.split(text, '\n')
	
	def copy(self):
		new = DataNode(string.join(self.text, '\n'))
		return new
	
	def get_lines(self):
		return len(self.text)
	
	def add(self, subnode, before = None, after = None, index = None):
		raise Barren, self
	
	def __str__(self):
		return self.text[0] + '...'
	
	def set_data(self, text):
		text = string.strip(text)
		self.set_raw(string.split(text, '\n'))
	
	def set_raw(self, lines):
		self.add_undo(lambda self, t = self.text: self.set_raw(t))
		self.text = lines
