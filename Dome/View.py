from gtk import *
from support import *
from xml.dom.Node import Node
from xml.xpath import XPathParser, FT_EXT_NAMESPACE, Context
import re, string, types

class Beep(Exception):
	pass

# An view contains:
# - A ref to a DOM document
# - A current node
# - A root node
# - A chroot stack
# It does not have any display code. It does contain code to perform actions
# (actions affect the document AND the view state).

class View:
	def __init__(self, model):
		self.model = model
		self.chroots = []
		self.current = self.model.get_root()
		self.root = self.current
		model.add_view(self)
	
	def has_ancestor(self, node, ancestor):
		while node != ancestor:
			node = node.parentNode
			if not node:
				return FALSE
		return TRUE
	
	def update_all(self):
		# Is the root node still around?
		if not self.has_ancestor(self.root, self.model.get_root()):
			# No - reset everything
			print "[ lost root - using doc root ]"
			self.root = doc_root
			self.chroots = []
		
		# Is the current node still around?
		if not self.has_ancestor(self.current, self.root):
			# No - move to root
			print "[ lost current - using root ]"
			self.current = self.root
			return

		return
	
	def delete(self):
		self.model.remove_view(self)
		self.model = None
		self.current = None
	
	def home(self):
		"Move current to the display root."
		self.move_to_node(self.root_node)
	
	def move_to(self, node):
		if self.current == node:
			return

		self.current = node
	
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
	
	def set_display_root(self, root):
		self.root = root
		self.update_all()
	
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
			raise Exception('No Enter to undo!')

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
		if len(rt) == 0:
			raise Beep
		node = rt[0]
		#for x in rt:
			#if self.node_to_line[x] > self.current_line:
				#node = x
				#break
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
