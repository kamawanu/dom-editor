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

class Loop(Exception):
	def __str__(self):
		return "Adding node would create a loop"

class CantJoin(Exception):
	def __str__(self):
		return "Can only join a DataNode to another DataNode"

# Remove the namespace part
def strip_ns(name):
	i = string.find(name, ' ')
	if i != -1:
		return name[i + 1:]
	return name

class Node:
	def __init__(self):
		self.undo = []
		self.redo = []
		self.kids = []
		self.undoing = 0
		self.redoing = 0
		self.parent = None

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
	
	# Remove 'node' and inherit its children
	def flatten(self, node):
		for k in node.kids[:]:
			node.remove(k)
			self.add(k, before = node)
		self.remove(node)
	
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
	
	def search_for(self, pattern):
		if self.matches_wild(pattern):
			return self
		for k in self.kids:
			node = k.search_for(pattern)
			if node:
				return node
		return None
	
	def matches_wild(self, pattern):
		if pattern.type == '(tree)':
			return 1
		
		if not self.matches(pattern):
			return 0
		
		k = self.kids[:]
		p = pattern.kids[:]
		if len(k) != len(p):
			return 0
		while k:
			if not k.pop().matches_wild(p.pop()):
				return 0
		return 1

# A normal node which can contain subnodes, has a tag type, and may
# also be given attributes.
class TagNode(Node):
	def __init__(self, type, attribs = None):
		Node.__init__(self)

		if attribs == None:
			self.attribs = {}
		else:
			self.attribs = attribs
		self.type = type
	
	def copy(self):
		new = TagNode(self.type)
		new.attribs = self.attribs.copy()
		for k in self.kids:
			nk = k.copy()
			new.kids.append(nk)
			nk.parent = new
		return new
	
	def set_type(self, type):
		self.add_undo(lambda self, t = self.type: self.set_type(t))
		self.type = type
	
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
	
	def __str__(self):
		retval = strip_ns(self.type)
		for a in self.attribs.keys():
			retval = retval + \
				', %s="%s"' % (strip_ns(a), self.attribs[a])
		return retval
	
	def to_xml(self):
		d = '<' + self.type
		for a in self.attribs.keys():
			d = d + (' %s="%s"' % a, escape(self.attribs[a]))

		if self.kids == []:
			return d + '/>\n'
			
		d = d + '>'
		if len(self.kids) == 1:
			k = self.kids[0]
			if isinstance(k, DataNode) and len(k.text) == 1:
				return d + k.text[0] + ('</%s>' % self.type)

		d = d + '\n'
		for k in self.kids:
			d = d + k.to_xml()

		return d + ('</%s>\n' % self.type)
	
	def remove(self, child):
		i = self.kids.index(child)
		self.kids.remove(child)
		child.parent = None
		self.add_undo(lambda self, c = child, i = i:
					self.add(c, index = i))
	
	def matches(self, pattern):
		if pattern.type == '(tag)':
			return 1
		return self.type == pattern.type

# Contains several lines of text. Cannot have children.
# In:
# 	<note>Text<br/>More Text</note>
# the tree is:
# TagNode(note)
#   |--DataNode(Text)
#   |--TagNode(p/)
#   \--DataNode(More Text)
class DataNode(Node):
	def __init__(self, text):
		Node.__init__(self)
		self.text = string.split(text, '\n')
	
	def copy(self):
		new = DataNode(string.join(self.text, '\n'))
		return new
	
	def get_lines(self):
		return len(self.text)
	
	def __str__(self):
		return self.text[0] + '...'
	
	def set_data(self, text):
		text = string.strip(text)
		self.set_raw(string.split(text, '\n'))
	
	def set_raw(self, lines):
		self.add_undo(lambda self, t = self.text: self.set_raw(t))
		self.text = lines
	
	def join(self):
		next = self.next_sibling()
		if next == None or not isinstance(next, DataNode):
			raise CantJoin, self
		self.set_raw(self.text + next.text)
		self.parent.remove(next)
	
	def split(self, line):
		new = DataNode(string.join(self.text[line:], '\n'))
		self.parent.add(new, after = self)
		self.set_raw(self.text[:line])
	
	def to_xml(self):
		return string.join(self.text, '\n') + '\n'
	
	def matches(self, pattern):
		if pattern.type == '(text)':
			return 1
		if isinstance(pattern, DataNode):
			return 1
		return 0
