from gtk import *
from support import *
from xml.dom import Node, ext
from xml.xpath import XPathParser, FT_EXT_NAMESPACE, Context
import os, re, string, types
import urlparse
import Html

from Program import Op
from Beep import Beep
from GetArg import GetArg
import Exec

DOME_NS = 'http://www.ecs.soton.ac.uk/~tal00r/Dome'

# An view contains:
# - A ref to a DOM document
# - A current node
# - A root node
# - A chroot stack
# It does not have any display code. It does contain code to perform actions
# (actions affect the document AND the view state).

def same(a, b):
	"Recursivly compare two nodes."
	if a.nodeType != b.nodeType or a.nodeName != b.nodeName:
		return FALSE
	if a.nodeValue != b.nodeValue:
		return FALSE
	aks = a.childNodes
	bks = b.childNodes
	if len(aks) != len(bks):
		return FALSE
	for (ak, bk) in map(None, aks, bks):
		if not same(ak, bk):
			return FALSE
	return TRUE

class InProgress(Exception):
	"Throw this if the operation will complete later..."

class View:
	def __init__(self, model):
		self.displays = []
		self.lists = []
		self.model = model
		self.chroots = []
		self.root = self.model.get_root()
		self.current_nodes = [self.root]
		self.clipboard = None
		self.current_attrib = None
		model.add_view(self)

		self.exec_point = None		# None, or (Op, Exit)
		self.rec_point = None		# None, or (Op, Exit)
		self.op_in_progress = None
	
	def __getattr__(self, attr):
		if attr == 'current':
			if len(self.current_nodes) == 1:
				return self.current_nodes[0]
			raise Exception('This operation required exactly one selected node!')
		raise Exception('Bad View attribute "%s"' % attr)

	def set_exec(self, pos):
		if self.op_in_progress:
			report_error("Operation in progress...")
			return
		self.exec_point = pos
		for l in self.lists:
			l.update_points()

	def set_rec(self, pos):
		self.rec_point = pos
		for l in self.lists:
			l.update_points()
	
	def record_at_point(self):
		if not self.exec_point:
			report_error("No current point!")
			return
		self.set_rec(self.exec_point)
		self.set_exec(None)

	def toggle_record(self):
		"Start or stop recording"
		if self.rec_point:
			self.set_rec(None)
		else:
			# XXX
			node = self.current_nodes[0]
			self.recording_where = self.model.macro_list.record_new(node.nodeName).start
			self.recording_exit = 'next'

	def may_record(self, action):
		"Perform and, possibly, record this action"
		rec = self.rec_point

		exit = 'next'
		try:
			self.do_action(action)
		except Beep:
			gdk_beep()
			(type, val, tb) = sys.exc_info()
			if not val.may_record:
				return 0
			exit = 'fail'

		# Only record if we were recording when this action started
		if rec:
			(op, old_exit) = rec
			new_op = Op(op.program, action)
			op.link_to(new_op, old_exit)
			self.set_rec((new_op, exit))
	
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
		if old in self.current_nodes:
			self.current_nodes.remove(old)
			self.current_nodes.append(new)
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
		for n in self.current_nodes[:]:
			if not self.has_ancestor(n, self.root):
				# No - remove
				self.current_nodes.remove(n)
		if not self.current_nodes:
			self.current_nodes = [self.root]

		if not (self.has_ancestor(node, self.root) or self.has_ancestor(self.root, node)):
			print "[ change to %s doesn't affect us (root %s) ]" % (node, self.root)
			return

		for display in self.displays:
			display.update_all(node)
	
	def delete(self):
		self.model.remove_view(self)
		self.model = None
		self.current = None
	
	def home(self):
		"Move current to the display root."
		self.move_to(self.root_node)
	
	# 'nodes' may be either a node or a list of nodes.
	# If it's a single node, then an 'attrib' node may also be specified
	def move_to(self, nodes, attrib = None):
		if self.current_nodes == nodes:
			return

		if attrib and attrib.nodeType != Node.ATTRIBUTE_NODE:
			raise Exception('attrib not of type ATTRIBUTE_NODE!')

		if type(nodes) != types.ListType:
			nodes = [nodes]

		old_nodes = self.current_nodes
		self.current_nodes = nodes

		self.current_attrib = attrib

		for display in self.displays:
			display.move_from(old_nodes)
	
	def move_prev_sib(self):
		if self.current == self.root or not self.current.previousSibling:
			raise Beep
		self.move_to(self.current.previousSibling)
	
	def move_next_sib(self):
		if self.current == self.root or not self.current.nextSibling:
			raise Beep
		self.move_to(self.current.nextSibling)
	
	def move_left(self):
		new = []
		for n in self.current_nodes:
			if n == self.root:
				raise Beep
			if n not in new:
				new.append(n.parentNode)
		self.move_to(new)
	
	def move_right(self):
		new = []
		for n in self.current_nodes:
			kids = n.childNodes
			if kids:
				new.append(kids[0])
			else:
				raise Beep
		self.move_to(new)
	
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
		exit = 'next'
		try:
			new = apply(fn, action[1:])
		except InProgress:
			return
		except Beep:
			if not self.op_in_progress:
				raise
			exit = 'fail'
			new = None
		if self.op_in_progress:
			op = self.op_in_progress
			self.set_oip(None)
			self.set_exec((op, exit))
		if new:
			self.move_to(new)
	
	# Actions...

	def do_global(self, pattern):
		p = XPathParser.XPathParser()	
		path = p.parseExpression(pattern)

		if len(self.current_nodes) != 1:
			self.move_to(self.root)
		ns = {}
		if not ns:
			ns = ext.GetAllNs(self.current_nodes[0])
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(self.current, [self.current], processorNss = ns)
		self.global_set = path.select(c)
		self.move_to(self.global_set)
		
	def do_search(self, pattern, ns = None, toggle = FALSE):
		p = XPathParser.XPathParser()	
		path = p.parseExpression(pattern)

		if len(self.current_nodes) == 0:
			src = self.root
		else:
			src = self.current_nodes[-1]
		if not ns:
			ns = ext.GetAllNs(src)
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(src, [src], processorNss = ns)
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
			print "    (namespaces were '%s')" % ns
			raise Beep
		if toggle:
			new = self.current_nodes[:]
			if node in new:
				new.remove(node)
			else:
				new.append(node)
			self.move_to(new)
		else:
			self.move_to(node)
	
	def do_text_search(self, pattern):
		return self.do_search("//text()[ext:match('%s')]" % pattern)

	def subst(self, replace, with):
		"re search and replace on the current node"
		for n in self.current_nodes:
			if n.nodeType == Node.TEXT_NODE:
				new = re.sub(replace, with, n.data)
				self.model.set_data(n, new)
			else:
				self.move_to(n)
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
		# XXX
		def ask_cb(result, self = self):
			self.clipboard = self.model.doc.createTextNode(result)
			if self.exec_state.where and not self.recording_where:
				self.exec_state.unfreeze('next')
		self.exec_state = Exec.exec_state	# XXX
		if self.exec_state.where and not self.recording_where:
			self.exec_state.freeze()
		GetArg('Input:', ask_cb, [q])

	def python_to_node(self, data):
		"Convert a python data structure into a tree and return the root."
		if type(data) == types.ListType:
			list = self.model.doc.createElementNS(DOME_NS, 'dome:list')
			for x in data:
				list.appendChild(self.python_to_node(x))
			return list
		return self.model.doc.createTextNode(str(data))
	
	def yank(self):
		if self.current_attrib:
			a = self.current_attrib
			self.clipboard = self.model.doc.createElementNS(DOME_NS, 'attribute')
			n = self.model.doc.createElementNS(DOME_NS, 'dome:namespaceURI')
			n.appendChild(self.model.doc.createTextNode(a.namespaceURI))
			self.clipboard.appendChild(n)
			n = self.model.doc.createElementNS(DOME_NS, 'dome:name')
			n.appendChild(self.model.doc.createTextNode(a.localName))
			self.clipboard.appendChild(n)
			n = self.model.doc.createElementNS(DOME_NS, 'dome:value')
			n.appendChild(self.model.doc.createTextNode(a.value))
			self.clipboard.appendChild(n)
		else:
			self.clipboard = self.model.doc.createDocumentFragment()
			for n in self.current_nodes:
				self.clipboard.appendChild(n.cloneNode(deep = 1))
		
		print "Clip now", self.clipboard
	
	def delete_node(self):
		nodes = self.current_nodes[:]
		if not nodes:
			return
		self.yank()
		if self.current_attrib:
			ca = self.current_attrib
			self.current_attrib = None
			self.model.set_attrib(self.current, ca.namespaceURI, ca.localName, None)
			return
		new = []
		for x in nodes:
			if x != self.root:
				p = x.parentNode
				if p not in new:
					new.append(p)
		if len(new) == 0:
			raise Beep
		for x in nodes:
			if self.has_ancestor(x, self.root):
				self.model.delete_node(x)
		self.move_to(new)
	
	def undo(self):
		self.model.undo(self.root)

	def redo(self):
		self.model.redo(self.root)

	def play(self, macro_name):
		print "Play", macro_name
		self.exec_state = Exec.exec_state	# XXX
		self.exec_state.play(macro_name)

	def map(self, macro_name):
		print "Map", macro_name

		nodes = self.current_nodes[:]
		inp = [nodes, None]
		def next(self = self, macro_name = macro_name, inp = inp):
			nodes, next = inp
			self.move_to(nodes[0])
			print "Next:", self.current
			del nodes[0]
			self.exec_state = Exec.exec_state	# XXX
			if not nodes:
				next = None
			self.exec_state.play(macro_name, when_done = next)
		inp[1] = next
		next()

	def change_node(self, new_data):
		node = self.current
		if node.nodeType == Node.TEXT_NODE or node.nodeType == Node.COMMENT_NODE:
			self.model.set_data(node, new_data)
		else:
			if ':' in new_data:
				(prefix, localName) = string.split(new_data, ':', 1)
			else:
				(prefix, localName) = ('', new_data)
			namespaceURI = self.model.prefix_to_namespace(self.current, prefix)
			self.model.set_name(node, namespaceURI, new_data)

	def add_node(self, where, data):
		cur = self.current
		if where[1] == 'e':
			if ':' in data:
				(prefix, localName) = string.split(data, ':', 1)
			else:
				(prefix, localName) = ('', data)
			namespaceURI = self.model.prefix_to_namespace(self.current, prefix)
			new = self.model.doc.createElementNS(namespaceURI, data)
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
				if uri.find('//') != -1 or uri.find('.htm') != -1:
					break
		if not uri:
			print "Can't suck", node
			raise Beep
		if uri.find('//') == -1:
			print "Relative URI..."
			p = node
			base = None
			while p:
				if p.hasAttributeNS(DOME_NS, 'uri'):
					base = p.getAttributeNS(DOME_NS, 'uri')
					break
				p = p.parentNode
			if base:
				print "Base URI is:", base
				uri = urlparse.urljoin(base, uri)
			else:
				print "Warning: Can't find 'uri' attribute!"

		command = "lynx -source '%s' | tidy" % uri
		print command
		cout = os.popen(command)

		reader = Html.Reader()
		root = reader.fromStream(cout)
		cout.close()
		new = html_to_xml(node.ownerDocument, root)
		new.setAttributeNS(DOME_NS, 'dome:uri', uri)
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
		self.model.insert_after(node, new)
	
	def put_replace(self):
		node = self.current
		if self.clipboard == None:
			raise Beep
		if self.current_attrib:
			if self.clipboard.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
				value = self.clipboard.childNodes[0].data
			else:
				value = self.clipboard.data
			a = self.current_attrib
			self.model.set_attrib(node, a.namespaceURI, a.localName, value)
			return
		if self.clipboard.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
			if len(self.clipboard.childNodes) != 1:
				raise Beep
			new = self.clipboard.childNodes[0].cloneNode(deep = 1)
		else:
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
	
	def yank_value(self):
		if not self.current_attrib:
			raise Beep
		value = self.current_attrib.value
		self.clipboard = self.model.doc.createTextNode(value)
		print "Clip now", self.clipboard
	
	def yank_attribs(self, name):
		self.clipboard = self.model.doc.createDocumentFragment()
		if name:
			if not self.current.hasAttribute(name):
				raise Beep
			attribs = [self.current.getAttributeNode(name)]
		else:
			attribs = []
			for a in self.current.attributes:
				attribs.append(a)

		# Make sure the attributes always come out in the same order
		# (helps with macros).
		def by_name(a, b):
			diff = cmp(a.name, b.name)
			if diff == 0:
				diff = cmp(a.namespaceURI, b.namespaceURI)
			return diff
			
		attribs.sort(by_name)
		for a in attribs:
			n = self.model.doc.createElementNS(a.namespaceURI, a.nodeName)
			n.appendChild(self.model.doc.createTextNode(a.value))
			self.clipboard.appendChild(n)
		print "Clip now", self.clipboard
	
	def paste_attribs(self):
		if self.clipboard.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
			attribs = self.clipboard.childNodes
		else:
			attribs = [self.clipboard]
		new = []
		def get(a, name):
			return a.getElementsByTagNameNS(DOME_NS, name)[0].childNodes[0].data
		for a in attribs:
			try:
				new.append((a.namespaceURI, a.nodeName, a.childNodes[0].data))
			except:
				raise Beep
		for node in self.current_nodes:
			for (ns, local, value) in new:
				self.model.set_attrib(node, ns, local, value)
	
	def compare(self):
		"Ensure that all selected nodes have the same value."
		if len(self.current_nodes) < 2:
			raise Beep		# Not enough nodes!
		base = self.current_nodes[0]
		for n in self.current_nodes[1:]:
			if not same(base, n):
				raise Beep(may_record = 1)
	
	def fail(self):
		raise Beep(may_record = 1)
	
	def attribute(self, namespace = None, attrib = None):
		if attrib is None:
			self.move_to(self.current)
			return

		print "(ns, attrib)", `namespace`, attrib

		if self.current.hasAttributeNS(namespace, attrib):
			self.move_to(self.current,
				self.current.getAttributeNodeNS(namespace, attrib))
		else:
			raise Beep()
	
	def set_attrib(self, namespaceURI, name, value):
		# 'name' must include the prefix if namespaceURI is not ''
		self.model.set_attrib(self.current, namespaceURI, name, value)
		self.move_to(self.current, self.current.getAttributeNodeNS(namespaceURI, name))

	def do_one_step(self, done = None):
		"Execute the next op after exec_point, then position the point "
		"on one of the exits and call done(). May return before the operation"
		"is complete."
		if self.op_in_progress:
			report_error("Already executing something.")
			return
		if not self.exec_point:
			report_error("No current playback point.")
			return
		(op, exit) = self.exec_point
		next = getattr(op, exit)
		if not next:
			report_error("Nothing more to do.")
			return
		self.set_oip(next)
		self.do_action(next.action)

	def set_oip(self, op):
		if op:
			self.set_exec(None)
		self.op_in_progress = op
		for l in self.lists:
			l.set_oip()
