from gtk import *
import GDK
from support import *
from xml.dom import Node, ext
from xml import xpath
from xml.xpath import FT_EXT_NAMESPACE, Context
from xml.dom.ext.reader import PyExpat
import os, re, string, types
import urlparse
import Html
from StringIO import StringIO
from Canvas import Canvas

from Program import Op
from Beep import Beep
from GetArg import GetArg

import time

DOME_NS = 'http://www.ecs.soton.ac.uk/~tal00r/Dome'

def elements(node):
	out = []
	for x in node.childNodes:
		if x.nodeType == Node.ELEMENT_NODE:
			out.append(x)
	return out

# An view contains:
# - A ref to a DOM document
# - A set of current nodes
# - A root node
# - A chroot stack
# It does not have any display code. It does contain code to perform actions
# (actions affect the document AND the view state).

# These actions can be repeated using '.'
record_again = [
	"do_global",
	"subst",
	"python",
	"ask",
	"yank",
	"shallow_yank",
	"delete_node",
	"play",
	"map",
	"change_node",
	"add_node",
	"suck",
	"put_before",
	"put_after",
	"put_replace",
	"put_as_child",
	"yank_value",
	"yank_attribs",
	"paste_attribs",
	"compare",
	"fail",
	"attribute",
	"set_attrib",
	"add_attrib",
	"soap_send",
	"show_canvas",
	"show_html",
]

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
class Done(Exception):
	"Thrown when the chain is completed successfully"

class View:
	def __init__(self, model, program):
		self.root_program = program
		self.root = None
		self.displays = []
		self.lists = []
		self.single_step = 1	# 0 = Play   1 = Step-into   2 = Step-over
		self.model = None
		self.chroots = []
		self.current_nodes = []
		self.clipboard = None
		self.current_attrib = None

		self.exec_point = None		# None, or (Op, Exit)
		self.rec_point = None		# None, or (Op, Exit)
		self.op_in_progress = None
		self.idle_cb = 0
		self.callback_on_return = None	# Called when there are no more Ops...
		self.in_callback = 0		# (not the above callback - this is the playback one)
		self.innermost_failure = None
		self.call_on_done = None	# Called when there is nowhere to return to
		self.exec_stack = []		# Ops we are inside (display use only)

		self.breakpoints = {}		# (op, exit) keys, values don't matter
		self.current_nodes = []
		self.set_model(model)
	
	def get_current(self):
		if len(self.current_nodes) == 1:
			return self.current_nodes[0]
		raise Exception('This operation required exactly one selected node!')
		
	def set_model(self, model):
		if self.root:
			self.move_to([])
			self.model.unlock(self.root)
		self.root = None
		if self.model:
			self.model.remove_view(self)
		self.model = model
		model.add_view(self)
		self.set_display_root(self.model.get_root())
		self.move_to(self.root)
	
	def running(self):
		return self.idle_cb != 0 or self.in_callback

	def run_new(self, callback = None):
		"Reset the playback system (stack, step-mode and point)."
		"Call callback(exit) when execution finishes."
		if self.idle_cb:
			idle_remove(self.idle_cb)
			self.idle_cb = 0
		self.single_step = 0
		self.innermost_failure = None
		self.call_on_done = callback
		self.callback_on_return = None
		while self.exec_stack:
			self.pop_stack()

	def push_stack(self, op):
		if not isinstance(op, Op):
			raise Exception('push_stack: not an Op', op)
		self.exec_stack.append(op)
		for l in self.lists:
			l.update_stack(op)

	def pop_stack(self):
		op = self.exec_stack.pop()
		for l in self.lists:
			l.update_stack(op)

	def set_exec(self, pos):
		if self.op_in_progress:
			raise Exception("Operation in progress...")
		if pos and not isinstance(pos[0], Op):
			raise Exception("Not an (operation, exit) tuple", pos)
		self.exec_point = pos
		#if pos:
		#print "set_exec: %s:%s" % pos
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

	def stop_recording(self):
		if self.rec_point:
			self.set_exec(self.rec_point)
			self.set_rec(None)
		else:
			report_error("Not recording!")

	def may_record(self, action):
		"Perform and, possibly, record this action"
		rec = self.rec_point

		exit = 'next'
		try:
			self.do_action(action)
		except InProgress:
			pass
		except Beep:
			gdk_beep()
			(type, val, tb) = sys.exc_info()
			if not val.may_record:
				return 0
			exit = 'fail'

		# Only record if we were recording when this action started
		if rec:
			print "RECORD:", rec, action
			(op, old_exit) = rec
			new_op = Op(action)
			op.link_to(new_op, old_exit)
			self.set_rec((new_op, exit))
	
	def add_display(self, display):
		"Calls move_from(old_node) when we move and update_all() on updates."
		self.displays.append(display)
		print "Added:", self.displays
	
	def remove_display(self, display):
		self.displays.remove(display)
		print "Removed, now:", self.displays
		if not self.displays:
			self.delete()
	
	def update_replace(self, old, new):
		if old == self.root:
			self.root = new
		if old in self.current_nodes:
			self.model.lock(new)
			self.model.unlock(old)
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
			raise Exception('Root locking error!')
		
		# Is the current node still around?
		for n in self.current_nodes[:]:
			if not self.has_ancestor(n, self.root):
				# No - locking error!
				self.current_nodes.remove(n)
				raise Exception('Internal locking error on %s!' % n)

		if not (self.has_ancestor(node, self.root) or self.has_ancestor(self.root, node)):
			print "[ change to %s doesn't affect us (root %s) ]" % (node, self.root)
			return

		for display in self.displays:
			display.update_all(node)
	
	def delete(self):
		print "View deleted"
		self.move_to([])
		for l in self.lists:
			l.destroy()
		self.model.unlock(self.root)
		self.root = None
		self.model.remove_view(self)
		self.model = None
	
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

		for node in self.current_nodes:
			self.model.lock(node)
		for node in old_nodes:
			self.model.unlock(node)

		self.current_attrib = attrib

		for display in self.displays:
			display.move_from(old_nodes)
	
	def move_prev_sib(self):
		if self.get_current() == self.root or not self.get_current().previousSibling:
			raise Beep
		self.move_to(self.get_current().previousSibling)
	
	def move_next_sib(self):
		if self.get_current() == self.root or not self.get_current().nextSibling:
			raise Beep
		self.move_to(self.get_current().nextSibling)
	
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
		if not self.get_current().childNodes:
			raise Beep
		node = self.get_current().childNodes[0]
		while node.nextSibling:
			node = node.nextSibling
		self.move_to(node)
	
	def set_display_root(self, root):
		self.model.lock(root)
		if self.root:
			self.model.unlock(self.root)
		self.root = root
		self.update_all(root)
	
	def enter(self):
		"""Change the display root to a COPY of the selected node.
		Call Leave to check changes back in."""
		node = self.get_current()
		self.chroots.append((self.model, node))
		self.set_model(self.model.lock_and_copy(node))
	
	def leave(self):
		"""Undo the effect of the last chroot()."""
		if not self.chroots:
			raise Beep

		(old_model, old_node) = self.chroots.pop()
		
		copy = old_model.doc.importNode(self.model.get_root(), deep = 1)
		old_model.unlock(old_node)
		old_model.replace_node(old_node, copy)
		self.set_model(old_model)

	def do_action(self, action):
		"'action' is a tuple (function, arg1, arg2, ...)"
		"Performs the action. Returns if action completes, or raises "
		"InProgress if not (will call resume() later)."
		if action[0] in record_again:
			self.last_action = action
		elif action[0] == 'again':
			action = self.last_action
		fn = getattr(self, action[0])
		exit = 'next'
		#print "DO:", action[0]
		self.model.mark()
		try:
			new = apply(fn, action[1:])
		except InProgress:
			raise
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
	
	def do_one_step(self):
		"Execute the next op after exec_point, then:"
		"- position the point on one of the exits return."
		"- if there is no op to perform, call callback_on_return() or raise Done."
		"- if the operation is started but not complete, raise InProgress and "
		"  arrange to resume() later."
		if self.op_in_progress:
			report_error("Already executing something.")
			raise Done()
		if not self.exec_point:
			report_error("No current playback point.")
			raise Done()
		(op, exit) = self.exec_point

		if self.single_step == 0 and self.breakpoints.has_key(self.exec_point):
			print "Hit a breakpoint! At " + time.ctime(time.time())
			self.single_step = 1
			return
		
		next = getattr(op, exit)
		if next:
			self.set_oip(next)
			self.do_action(next.action)	# May raise InProgress
			return

		if exit == 'fail' and not self.innermost_failure:
			print "Setting innermost_failure"
			self.innermost_failure = op

		if self.callback_on_return:
			cb = self.callback_on_return
			self.callback_on_return = None
			cb()
		else:
			raise Done()

	def set_oip(self, op):
		if op:
			self.set_exec(None)
		self.op_in_progress = op
		for l in self.lists:
			l.update_points()

	# Actions...

	def do_global(self, pattern):
		if len(self.current_nodes) != 1:
			self.move_to(self.root)
		ns = {}
		if not ns:
			ns = ext.GetAllNs(self.current_nodes[0])
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(self.get_current(), [self.get_current()], processorNss = ns)
		self.move_to(xpath.Evaluate(pattern, context = c))
		
	def do_search(self, pattern, ns = None, toggle = FALSE):
		if len(self.current_nodes) == 0:
			src = self.root
		else:
			src = self.current_nodes[-1]
		if not ns:
			ns = ext.GetAllNs(src)
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(src, [src], processorNss = ns)
		rt = xpath.Evaluate(pattern, context = c)
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
		if self.get_current().nodeType == Node.TEXT_NODE:
			vars = {'x': self.get_current().data, 're': re, 'sub': re.sub, 'string': string}
			result = eval(expr, vars)
			new = self.python_to_node(result)
			self.model.replace_node(self.get_current(), new)
		else:
			raise Beep

	def resume(self, exit = 'next'):
		"After raising InProgress, call this to start moving again."
		if self.op_in_progress:
			op = self.op_in_progress
			self.set_oip(None)
			self.set_exec((op, exit))
			if not self.single_step:
				self.sched()
		else:
			print "(nothing to resume)"
		
	def ask(self, q):
		def ask_cb(result, self = self):
			if result is None:
				exit = 'fail'
			else:
				self.clipboard = self.model.doc.createTextNode(result)
				exit = 'next'
			self.resume(exit)
		box = GetArg('Input:', ask_cb, [q], destroy_return = 1)
		raise InProgress

	def python_to_node(self, data):
		"Convert a python data structure into a tree and return the root."
		if type(data) == types.ListType:
			list = self.model.doc.createElementNS(DOME_NS, 'dome:list')
			for x in data:
				list.appendChild(self.python_to_node(x))
			return list
		return self.model.doc.createTextNode(str(data))
	
	def yank(self, deep = 1):
		if self.current_attrib:
			a = self.current_attrib

			self.clipboard = self.model.doc.createElementNS(a.namespaceURI, a.nodeName)
			self.clipboard.appendChild(self.model.doc.createTextNode(a.value))
		else:
			self.clipboard = self.model.doc.createDocumentFragment()
			for n in self.current_nodes:
				c = n.cloneNode(deep = deep)
				print n, "->", c
				self.clipboard.appendChild(c)
		
		print "Clip now", self.clipboard
	
	def shallow_yank(self):
		self.yank(deep = 0)
	
	def delete_node(self):
		nodes = self.current_nodes[:]
		if not nodes:
			return
		self.yank()
		if self.current_attrib:
			ca = self.current_attrib
			self.current_attrib = None
			self.model.set_attrib(self.get_current(), ca.namespaceURI, ca.localName, None)
			return
		self.move_to([])	# Makes things go *much* faster!
		new = []
		for x in nodes:
			p = x.parentNode
			print "Delete %s, parent %s" % (x, p)
			if p not in new:
				new.append(p)
		self.move_to(new)
		self.model.delete_nodes(nodes)
	
	def undo(self):
		self.move_to([])
		self.model.undo(self.root)

	def redo(self):
		self.move_to([])
		self.model.redo(self.root)
	
	def default_done(self, exit):
		"Called when execution of a program returns. op_in_progress has been "
		"restored - move to the exit."
		print "default_done(%s)" % exit
		if self.op_in_progress:
			op = self.op_in_progress
			self.set_oip(None)
			self.set_exec((op, exit))
		else:
			print "No operation to return to!"
			c = self.call_on_done
			if c:
				self.call_on_done = None
				c(exit)
			raise Done()

	def play(self, name, done = None):
		"Play this macro. When it returns, restore the current op_in_progress (if any)"
		"and call done(exit). Default for done() moves exec_point."
		"done() is called from do_one_step() - usual rules apply."
		prog = self.name_to_prog(name)
		self.innermost_failure = None

		if not done:
			done = self.default_done

		def cbor(self = self, op = self.op_in_progress, done = done,
				name = name,
				old_cbor = self.callback_on_return,
				old_ss = self.single_step):
			"We're in do_one_step..."

			print "Return from '%s'..." % name

			if old_ss == 2 and self.single_step == 0:
				self.single_step = old_ss
			self.callback_on_return = old_cbor

			o, exit = self.exec_point
			if op:
				print "Resume op '%s' (%s)" % (op.program.name, op)
				self.pop_stack()
				self.set_oip(op)
			return done(exit)

		self.callback_on_return = cbor

		if self.single_step == 2:
			self.single_step = 0
			
		if self.op_in_progress:
			self.push_stack(self.op_in_progress)
			self.set_oip(None)
		self.set_exec((prog.start, 'next'))
		self.sched()
		raise InProgress
	
	def sched(self):
		if self.op_in_progress:
			raise Exception("Operation in progress")
		if self.idle_cb:
			raise Exception("Already playing!")
		self.idle_cb = idle_add(self.play_callback)

	def play_callback(self):
		idle_remove(self.idle_cb)
		self.idle_cb = 0
		try:
			self.in_callback = 1
			try:
				self.do_one_step()
			finally:
				self.in_callback = 0
		except Done:
			print "Done, at " + time.ctime(time.time())
			self.run_new()
			return 0
		except InProgress:
			print "InProgress"
			return 0
		except:
			type, val, tb = sys.exc_info()
			list = traceback.extract_tb(tb)
			stack = traceback.format_list(list[-2:])
			ex = traceback.format_exception_only(type, val) + ['\n\n'] + stack
			traceback.print_exception(type, val, tb)
			print "Error in do_one_step(): stopping playback"
			node = self.op_in_progress
			self.set_oip(None)
			self.set_exec((node, 'fail'))
			return 0
		if self.op_in_progress or self.single_step:
			return 0
		self.sched()
		return 0

	def map(self, name):
		# XXX - doesn't work always from a macro?
		print "Map", name

		nodes = self.current_nodes[:]
		inp = [nodes, None]	# Nodes, next
		def next(exit = exit, self = self, name = name, inp = inp):
			"This is called while in do_one_step() - normal rules apply."
			nodes, next = inp
			print "Map: next (%d to go)" % len(nodes)
			if exit == 'fail':
				print "Map: nodes remaining, but an error occurred..."
				return self.default_done(exit)
			self.move_to(nodes[0])
			print "Next:", self.get_current()
			del nodes[0]
			if not nodes:
				next = None
			print "Map: calling play (%d after this)" % len(nodes)
			self.play(name, done = next)		# Should raise InProgress
		if nodes is self.current_nodes:
			raise Exception("Slice failed!")
		inp[1] = next
		next('next')
	
	def name_to_prog(self, name):
		comps = string.split(name, '/')
		prog = self.root_program
		if prog.name != comps[0]:
			raise Exception("No such program as '%s'!" % name)
		del comps[0]
		while comps:
			prog = prog.subprograms[comps[0]]
			del comps[0]
		return prog

	def change_node(self, new_data):
		node = self.get_current()
		if node.nodeType == Node.TEXT_NODE or node.nodeType == Node.COMMENT_NODE:
			self.model.set_data(node, new_data)
		else:
			if ':' in new_data:
				(prefix, localName) = string.split(new_data, ':', 1)
			else:
				(prefix, localName) = ('', new_data)
			namespaceURI = self.model.prefix_to_namespace(self.get_current(), prefix)
			self.model.set_name(node, namespaceURI, new_data)

	def add_node(self, where, data):
		cur = self.get_current()
		if where[1] == 'e':
			if ':' in data:
				(prefix, localName) = string.split(data, ':', 1)
			else:
				(prefix, localName) = ('', data)
			namespaceURI = self.model.prefix_to_namespace(self.get_current(), prefix)
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
		node = self.get_current()

		if node.nodeType == Node.TEXT_NODE:
			uri = node.nodeValue
		else:
			if self.current_attrib:
				uri = self.current_attrib.value
			elif node.hasAttributeNS('', 'uri'):
				uri = node.getAttributeNS('', 'uri')
			else:
				for attr in node.attributes:
					uri = attr.value
					if uri.find('//') != -1 or uri.find('.htm') != -1:
						break
		if not uri:
			print "Can't suck", node
			raise Beep
		if uri.find('//') == -1:
			base = self.model.get_base_uri(node)
			print "Relative URI..."
			if base:
				print "Base URI is:", base
				uri = urlparse.urljoin(base, uri)
			else:
				print "Warning: Can't find 'uri' attribute!"

		command = "w3m -dump_source '%s' | tidy -asxml 2>/dev/null" % uri

		def done(root, self = self, uri = uri):
			node = self.get_current()
			new = node.ownerDocument.importNode(root.documentElement, deep = 1)
			new.setAttributeNS('', 'uri', uri)
			self.model.replace_node(node, new)
			print "Loaded."
			self.resume('next')
		self.dom_from_command(command, done)
		raise InProgress
	
	def dom_from_command(self, command, callback = None):
		"""Execute shell command 'command' in the background.
		Parse the output as XML. When done, call callback(doc_root)."""
		print command
		cout = os.popen(command)
	
		all = ["", None]
		def got_html(src, cond, all = all, self = self, cb = callback):
			data = src.read(100)
			if data:
				all[0] += data
				return
			input_remove(all[1])
			src.close()
			reader = PyExpat.Reader()
			print "Parsing..."
			
			try:
				root = reader.fromStream(StringIO(all[0]))
				ext.StripHtml(root)
			except:
				report_exception()
				root = None
			cb(root)
			
		all[1] = input_add(cout, GDK.INPUT_READ, got_html)
	
	def put_before(self):
		node = self.get_current()
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			self.model.insert_before(node, new)
		except:
			raise Beep

	def put_after(self):
		node = self.get_current()
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		self.model.insert_after(node, new)
	
	def put_replace(self):
		node = self.get_current()
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
		node = self.get_current()
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		if new.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
			to = []
			for n in new.childNodes:
				to.append(n)
		else:
			to = new
		try:
			self.model.insert(node, new, index = 0)
		except:
			raise Beep

		self.move_to(to)
	
	def yank_value(self):
		if not self.current_attrib:
			raise Beep
		value = self.current_attrib.value
		self.clipboard = self.model.doc.createTextNode(value)
		print "Clip now", self.clipboard
	
	def yank_attribs(self, name):
		self.clipboard = self.model.doc.createDocumentFragment()
		if name:
			if not self.get_current().hasAttribute(name):
				raise Beep
			attribs = [self.get_current().getAttributeNode(name)]
		else:
			attribs = []
			for a in self.get_current().attributes:
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
			self.move_to(self.get_current())
			return

		print "(ns, attrib)", `namespace`, attrib

		if self.get_current().hasAttributeNS(namespace, attrib):
			self.move_to(self.get_current(),
				self.get_current().getAttributeNodeNS(namespace, attrib))
		else:
			raise Beep()
	
	def set_attrib(self, value):
		a = self.current_attrib
		if not a:
			raise Beep()
		self.model.set_attrib(self.get_current(), a.namespaceURI, a.localName, value)
	
	def add_attrib(self, namespace, name):
		self.model.set_attrib(self.get_current(), namespace, name, "")
		self.move_to(self.get_current(), self.get_current().getAttributeNodeNS(namespace, name))
	
	def load_html(self, path):
		"Replace root with contents of this HTML file."
		print "Reading HTML..."
		command = "tidy -asxml '%s' 2>/dev/null" % path

		def done(root, self = self):
			print "Loaded!"
			new = self.root.ownerDocument.importNode(root.documentElement, deep = 1)

			if self.root:
				self.model.unlock(self.root)
			self.move_to([])
			self.model.replace_node(self.root, new)
			self.model.lock(new)
			self.root = new
			self.move_to(self.root)

		self.dom_from_command(command, done)

	def load_xml(self, path):
		"Replace root with contents of this XML file."
		reader = PyExpat.Reader()
		new_doc = reader.fromUri(path)

		new = self.model.doc.importNode(new_doc.documentElement, deep = 1)
		
		self.model.strip_space(new)

		if self.root:
			self.model.unlock(self.root)
		self.move_to([])
		self.model.replace_node(self.root, new)
		self.model.lock(new)
		self.root = new
		self.move_to(self.root)
	
	def show_html(self):
		from HTML import HTML
		HTML(self.model, self.get_current()).show()
	
	def show_canvas(self):
		Canvas(self, self.get_current()).show()
	
	def toggle_hidden(self):
		for node in self.current_nodes:
			if node.hasAttributeNS('', 'hidden'):
				new = None
			else:
				new = 'yes'
			self.model.set_attrib(node, '', 'hidden', new)
	
	def soap_send(self):
		copy = node_to_xml(self.get_current())
		env = copy.documentElement

		if env.namespaceURI != 'http://schemas.xmlsoap.org/soap/envelope/':
			report_error("Not a SOAP-ENV:Envelope (bad namespace)")
			raise Done()
		if env.localName != 'Envelope':
			report_error("Not a SOAP-ENV:Envelope (bad local name)")
			raise Done()

		if len(env.childNodes) != 2:
			report_error("SOAP-ENV:Envelope must have one header and one body")
			raise Done()

		kids = elements(env)
		head = kids[0]
		body = kids[1]

		if head.namespaceURI != 'http://schemas.xmlsoap.org/soap/envelope/' or \
		   head.localName != 'Head':
			report_error("First child must be a SOAP-ENV:Head element")
			raise Done()

		if body.namespaceURI != 'http://schemas.xmlsoap.org/soap/envelope/' or \
		   body.localName != 'Body':
			report_error("Second child must be a SOAP-ENV:Body element")
			raise Done()

		sft = None
		for header in elements(head):
			if header.namespaceURI == DOME_NS and header.localName == 'soap-forward-to':
				sft = header
				break
			print header.namespaceURI
			print header.localName

		if not sft:
			report_error("Head must contain a dome:soap-forward-to element")
			raise Done()

		dest = sft.childNodes[0].data
		parent = sft.parentNode
		if len(elements(parent)) == 1:
			sft = parent
			parent = sft.parentNode	# Delete the whole header
		parent.removeChild(sft)

		import httplib, urlparse

		(scheme, addr, path, p, q, f) = urlparse.urlparse(dest, allow_fragments = 0)
		if scheme != 'http':
			report_error("SOAP is only supported for 'http:' -- sorry!")
			raise Done()

		stream = StrGrab()
		ext.PrettyPrint(copy, stream = stream)
		message = stream.data

		conn = httplib.HTTP(addr)
		conn.putrequest("POST", path)
		conn.putheader('Content-Type', 'text/xml; charset="utf-8"')
		conn.putheader('Content-Length', str(len(message)))
		conn.putheader('SOAPAction', '')
		conn.endheaders()
		conn.send(message)
		(code, r_mess, r_headers) = conn.getreply()

		reply = conn.getfile().read()
		print "Got:\n", reply

		reader = PyExpat.Reader()
		new_doc = reader.fromString(reply)
		print new_doc

		new = self.model.doc.importNode(new_doc.documentElement, deep = 1)
		
		self.model.strip_space(new)

		old = self.get_current()
		self.move_to([])
		self.model.replace_node(old, new)
		self.move_to(new)

class StrGrab:
	data = ''

	def write(self, str):
		self.data += str
