from gtk import *
from support import *
from xml.dom.Node import Node
from xml.dom import ext
from xml.xpath import XPathParser, FT_EXT_NAMESPACE, Context
import os, re, string, types
import Html

from Beep import Beep
import Exec

# An view contains:
# - A ref to a DOM document
# - A current node
# - A root node
# - A chroot stack
# It does not have any display code. It does contain code to perform actions
# (actions affect the document AND the view state).

class View:
	def __init__(self, model):
		self.displays = []
		self.model = model
		self.chroots = []
		self.current = self.model.get_root()
		self.root = self.current
		self.clipboard = None
		model.add_view(self)
	
	def add_display(self, display):
		"Calls move_from(old_node) when we move and update_all() on updates."
		self.displays.append(display)
		print "Added:", self.displays
	
	def remove_display(self, display):
		self.displays.remove(display)
		print "Removed, now:", self.displays
	
	def update_replace(self, old, new):
		if old == self.root:
			self.root = new
		if old == self.current:
			self.current = new
			self.update_all(new.parentNode)
		else:
			self.update_all(new.parentNode)
		
	def has_ancestor(self, node, ancestor):
		while node != ancestor:
			node = node.parentNode
			if not node:
				return FALSE
		return TRUE
	
	def update_all(self, node):
		# Is the root node still around?
		if not self.has_ancestor(self.root, self.model.get_root()):
			# No - reset everything
			print "[ lost root - using doc root ]"
			self.root = self.model.doc.documentElement
			self.chroots = []
		
		# Is the current node still around?
		if not self.has_ancestor(self.current, self.root):
			# No - move to root
			print "[ lost current - using root ]"
			self.current = self.root

		if self.has_ancestor(node, self.root) or self.has_ancestor(self.root, node):
			for display in self.displays:
				display.update_all()
		else:
			print "[ change to %s doesn't affect us (root %s) ]" % (node, self.root)
	
	def delete(self):
		self.model.remove_view(self)
		self.model = None
		self.current = None
	
	def home(self):
		"Move current to the display root."
		self.move_to(self.root_node)
	
	def move_to(self, node):
		if self.current == node:
			return

		old_node = self.current
		self.current = node

		for display in self.displays:
			display.move_from(old_node)
	
	def move_prev_sib(self):
		if self.current == self.root or not self.current.previousSibling:
			raise Beep
		self.move_to(self.current.previousSibling)
	
	def move_next_sib(self):
		if self.current == self.root or not self.current.nextSibling:
			raise Beep
		self.move_to(self.current.nextSibling)
	
	def move_left(self):
		if self.current == self.root:
			raise Beep
		self.move_to(self.current.parentNode)
	
	def move_right(self):
		kids = self.current.childNodes
		if kids:
			self.move_to(kids[0])
		else:
			raise Beep
	
	def move_home(self):
		self.move_to(self.root)
	
	def move_end(self):
		if not self.current.childNodes:
			raise Beep
		node = self.current.childNodes[0]
		while node.nextSibling:
			node = node.nextSibling
		self.move_to(node)
	
	def set_display_root(self, root):
		self.root = root
		self.update_all(root)
	
	def enter(self):
		"Change the display root to the current node."
		n = 0
		node = self.current
		while node != self.root:
			n += 1
			node = node.parentNode
		self.chroots.append(n)
		self.set_display_root(self.current)
	
	def leave(self):
		"Undo the effect of the last chroot()."
		if not self.chroots:
			raise Beep

		n = self.chroots.pop()
		root = self.root
		while n > 0:
			n = n - 1
			root = root.parentNode
		self.set_display_root(root)

	def do_action(self, action):
		"'action' is a tuple (function, arg1, arg2, ...)"
		fn = getattr(self, action[0])
		new = apply(fn, action[1:])
		if new:
			self.move_to(new)
	
	# Actions...

	def do_search(self, pattern, ns = None):
		p = XPathParser.XPathParser()	
		path = p.parseExpression(pattern)

		if not ns:
			ns = {}
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(self.current, [self.current], processorNss = ns)
		rt = path.select(c)
		node = None
		for x in rt:
			if not self.has_ancestor(x, self.root):
				print "[ skipping search result above root ]"
				continue
			if not node:
				node = x
			#if self.node_to_line[x] > self.current_line:
				#node = x
				#break
		if not node:
			print "*** Search for '%s' failed" % pattern
			raise Beep
		self.move_to(node)

	def subst(self, replace, with):
		"re search and replace on the current node"
		if self.current.nodeType == Node.TEXT_NODE:
			new = re.sub(replace, with, self.current.data)
			self.model.set_data(self.current, new)
		else:
			raise Beep

	def python(self, expr):
		"Replace node with result of expr(old_value)"
		if self.current.nodeType == Node.TEXT_NODE:
			vars = {'x': self.current.data, 're': re, 'sub': re.sub, 'string': string}
			result = eval(expr, vars)
			new = self.python_to_node(result)
			self.model.replace_node(self.current, new)
		else:
			raise Beep

	def ask(self, q):
		def ask_cb(result, self = self):
			if result == 0:
				self.exec_state.unfreeze('next')
			elif result == 1:
				self.exec_state.unfreeze('fail')
		self.exec_state.freeze()
		get_choice(q, "Question:", ('Yes', 'No'), ask_cb)

	def python_to_node(self, data):
		"Convert a python data structure into a tree and return the root."
		if type(data) == types.ListType:
			list = self.model.doc.createElement('List')
			for x in data:
				list.appendChild(self.python_to_node(x))
			return list
		return self.model.doc.createTextNode(str(data))
	
	def yank(self):
		node = self.current
		self.clipboard = node.cloneNode(deep = 1)
		print "Clip now", self.clipboard
	
	def delete_node(self):
		node = self.current
		self.clipboard = node.cloneNode(deep = 1)
		print "Clip now", self.clipboard
		self.move_left()	# Exception raised if on the root...
		self.model.delete_node(node)
	
	def undo(self):
		self.model.undo(self.root)

	def redo(self):
		self.model.redo(self.root)

	def playback(self, macro_name):
		self.exec_state = Exec.exec_state	# XXX
		self.exec_state.play(macro_name)

	def change_node(self, new_data):
		node = self.current
		if node.nodeType == Node.TEXT_NODE:
			self.model.set_data(node, new_data)
		else:
			self.model.set_name(node, new_data)

	def add_node(self, where, data):
		cur = self.current
		if where[1] == 'e':
			new = self.model.doc.createElement(data)
		else:
			new = self.model.doc.createTextNode(data)
		
		try:
			if where[0] == 'i':
				self.model.insert_before(cur, new)
			elif where[0] == 'a':
				self.model.insert_after(cur, new)
			else:
				self.model.insert(cur, new)
		except:
			raise Beep

		self.move_to(new)

	def suck(self):
		node = self.current

		if node.nodeType == Node.TEXT_NODE:
			uri = node.nodeValue
		else:
			uri = None
			for attr in node.attributes:
				uri = attr.value
				if uri.find('//') != -1:
					break
		if not uri:
			print "Can't suck", node
			raise Beep
		command = "lynx -source '%s' | tidy" % uri
		print command
		cout = os.popen(command)

		reader = Html.Reader()
		root = reader.fromStream(cout)
		cout.close()
		ext.StripHtml(root)
		new = html_to_xml(node.ownerDocument, root)
		self.model.replace_node(node, new)
	
	def put_before(self):
		node = self.current
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			self.model.insert_before(node, new)
		except:
			raise Beep

	def put_after(self):
		node = self.current
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			self.model.insert_after(node, new)
		except:
			raise Beep

	def put_replace(self):
		node = self.current
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			self.model.replace_node(node, new)
		except:
			raise Beep

	def put_as_child(self):
		node = self.current
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			self.model.insert(node, new, index = 0)
		except:
			raise Beep
