from __future__ import nested_scopes

import GDK
from support import *
from rox import support
from xml.dom import Node, ext, XMLNS_NAMESPACE
from Ft.Xml import XPath
from Ft.Xml.XPath import FT_EXT_NAMESPACE, Context
from xml.dom.ext.reader import PyExpat
from Ft.Xml.cDomlette import implementation

import os, re, string, types
import urlparse
import Html
from StringIO import StringIO

from Program import Op
from Beep import Beep

import time
import urllib
import traceback

from constants import *

def elements(node):
	out = []
	for x in node.childNodes:
		if x.nodeType == Node.ELEMENT_NODE:
			out.append(x)
	return out

normal_chars = string.letters + string.digits + "-"

fast_global = re.compile('//([-A-Za-z][-A-Za-z0-9]*:)?[-A-Za-z][-A-Za-z0-9]*$')

def fix_broken_html(data):
	"""Pre-parse the data before sending to tidy to fix really really broken
stuff (eg, MS Word output). Returns None if data is OK"""
	if data.find('<o:p>') == -1:
		return 		# Doesn't need fixing?
	import re
	data = data.replace('<o:p></o:p>', '')
	data = re.sub('<!\[[^]]*\]>', '', data)
	return data

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
	"delete_node_no_clipboard",
	"delete_shallow",
	"play",
	"map",
	"change_node",
	"add_node",
	"suck",
	"http_post",
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
	"select_dups",
	"select_region",
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
	def __init__(self, model, callback_handlers = None):
		"""callback_handlers is an (idle_add, idle_remove) tuple"""
		self.root = None
		self.displays = []
		self.lists = []
		self.single_step = 1	# 0 = Play   1 = Step-into   2 = Step-over
		self.model = None
		self.chroots = []
		self.current_nodes = []
		self.clipboard = None
		self.current_attrib = None
		
		if not callback_handlers:
			import gtk
			self.idle_add, self.idle_remove = gtk.idle_add, gtk.idle_remove
		else:
			self.idle_add, self.idle_remove = callback_handlers

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
			self.model.root_program.watchers.remove(self)
		self.model = model
		self.model.root_program.watchers.append(self)
		model.add_view(self)
		self.set_display_root(self.model.get_root())
		self.move_to(self.root)
	
	def running(self):
		return self.idle_cb != 0 or self.in_callback

	def run_new(self, callback = None):
		"Reset the playback system (stack, step-mode and point)."
		"Call callback(exit) when execution finishes."
		if self.idle_cb:
			self.idle_remove(self.idle_cb)
			self.idle_cb = 0
		self.single_step = 0
		self.innermost_failure = None
		self.call_on_done = callback
		self.callback_on_return = None
		while self.exec_stack:
			self.pop_stack()
		self.status_changed()

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
			raise Exception("Not an (operation, exit) tuple: " + `pos`)
		self.exec_point = pos
		#if pos:
		#print "set_exec: %s:%s" % pos
		for l in self.lists:
			l.update_points()

	def set_rec(self, pos):
		self.rec_point = pos
		for l in self.lists:
			l.update_points()
		self.status_changed()
	
	def record_at_point(self):
		if not self.exec_point:
			support.report_error("No current point!")
			return
		self.set_rec(self.exec_point)
		self.set_exec(None)

	def stop_recording(self):
		if self.rec_point:
			self.set_exec(self.rec_point)
			self.set_rec(None)
		else:
			support.report_error("Not recording!")

	def may_record(self, action):
		"Perform and, possibly, record this action"
		rec = self.rec_point

		if rec:
			print "RECORD:", rec, action
			(op, old_exit) = rec
			new_op = Op(action)
			op.link_to(new_op, old_exit)
			self.set_exec(rec)
			try:
				self.do_one_step()
			except InProgress:
				self.set_rec((new_op, 'next'))
				return
			play_op, exit = self.exec_point
			# (do_one_step may have stopped recording)
			if self.rec_point:
				self.set_rec((new_op, exit))
				self.set_exec(None)
			return

		exit = 'next'
		try:
			self.do_action(action)
		except InProgress:
			pass
		except Beep:
			import gtk
			gtk.gdk_beep()
			(type, val, tb) = sys.exc_info()
			#if not val.may_record:
			#	return 0
			exit = 'fail'
		except:
			support.report_exception()
			raise
	
	def add_display(self, display):
		"Calls move_from(old_node) when we move and update_all() on updates."
		self.displays.append(display)
		#print "Added:", self.displays
	
	def remove_display(self, display):
		self.displays.remove(display)
		#print "Removed, now:", self.displays
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
		"""
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
			#print "[ change to %s doesn't affect us (root %s) ]" % (node, self.root)
			return
		"""

		for display in self.displays:
			display.update_all(node)
	
	def delete(self):
		#print "View deleted"
		self.model.root_program.watchers.remove(self)
		self.move_to([])
		for l in self.lists:
			l.destroy()
		self.model.unlock(self.root)
		self.root = None
		self.model.remove_view(self)
		self.model = None
	
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
			p = n.parentNode
			if p not in new:
				new.append(p)
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
		if node is self.root:
			raise Beep		# Locking problems if this happens...
		if self.model.doc is not node.ownerDocument:
			raise Exception('Current node not in view!')
		self.chroots.append((self.model, node))
		self.set_model(self.model.lock_and_copy(node))
	
	def leave(self):
		"""Undo the effect of the last chroot()."""
		if not self.chroots:
			raise Beep

		model = self.model

		(old_model, old_node) = self.chroots.pop()

		copy = old_model.doc.importNode(self.model.get_root(), 1)
		old_model.unlock(old_node)
		old_model.replace_node(old_node, copy)
		self.set_model(old_model)
		self.move_to([copy])

		if not model.views:
			model.undo_stack = None
			model.__dict__ = {}
			del model
			import gc
			gc.collect()

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
		except:
			if not self.op_in_progress:
				raise
			traceback.print_exc()
			exit = 'fail'
			new = None

		if self.op_in_progress:
			op = self.op_in_progress
			self.set_oip(None)
			self.set_exec((op, exit))
		if new:
			self.move_to(new)
	
	def breakpoint(self):
		if self.breakpoints.has_key(self.exec_point):
			return 1
		op = self.exec_point[0]
		if op.program.start == op and op.next == None:
			return 1		# Empty program
		return 0
	
	def do_one_step(self):
		"Execute the next op after exec_point, then:"
		"- position the point on one of the exits return."
		"- if there is no op to perform, call callback_on_return() or raise Done."
		"- if the operation is started but not complete, raise InProgress and "
		"  arrange to resume() later."
		if self.op_in_progress:
			support.report_error("Already executing something.")
			raise Done()
		if not self.exec_point:
			support.report_error("No current playback point.")
			raise Done()
		(op, exit) = self.exec_point

		if self.single_step == 0 and self.breakpoint():
			print "Hit a breakpoint! At " + time.ctime(time.time())
			if self.rec_point:
				self.set_rec(None)
			self.single_step = 1
			for l in self.lists:
				l.show_prog(op.program)
			return
		
		next = getattr(op, exit)
		if next:
			self.set_oip(next)
			self.do_action(next.action)	# May raise InProgress
			return

		if exit == 'fail' and not self.innermost_failure:
			#print "Setting innermost_failure on", op
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

	def fast_global(self, name):
		"Search for nodes with this name anywhere under the root (//name)"
		#print "Fast global", name
		if ':' in name:
			(prefix, localName) = string.split(name, ':', 1)
		else:
			(prefix, localName) = (None, name)
		if self.current_nodes:
			src = self.current_nodes[-1]
		else:
			src = self.root
		namespaceURI = self.model.prefix_to_namespace(src, prefix)
		select = []
		def add(node):
			if node.nodeType != Node.ELEMENT_NODE:
				return
			if node.localName == localName and node.namespaceURI == namespaceURI:
				select.append(node)
			map(add, node.childNodes)
		add(self.root)
		self.move_to(select)

	# Actions...

	def do_global(self, pattern):
		if len(self.current_nodes) != 1:
			self.move_to(self.root)
		if pattern[:2] == '//':
			if fast_global.match(pattern):
				self.fast_global(pattern[2:])
				return
		ns = {}
		if not ns:
			ns = ext.GetAllNs(self.current_nodes[0])
		ns['ext'] = FT_EXT_NAMESPACE
		ns['_'] = ns[None]
		#print "ns is", ns
		c = Context.Context(self.get_current(), processorNss = ns)
		from Ft.Xml.XPath import XPathParser
		code = XPathParser.new().parse(self.macro_pattern(pattern))
		#print code
		nodes = code.evaluate(c)
		#nodes = XPath.Evaluate(self.macro_pattern(pattern), contextNode = self.get_current())
		#print "Found", nodes
		self.move_to(nodes)

	def select_region(self, path, ns = None):
		if len(self.current_nodes) == 0:
			raise Beep
		src = self.current_nodes[-1]
		if not ns:
			ns = ext.GetAllNs(src)
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(src, [src], processorNss = ns)
		rt = XPath.Evaluate(path, context = c)
		node = None
		for x in rt:
			if not self.has_ancestor(x, self.root):
				print "[ skipping search result above root ]"
				continue
			if not node:
				node = x
		if not node:
			print "*** Search for '%s' in select_region failed" % path
			print "    (namespaces were '%s')" % ns
			raise Beep
		if node.parentNode != src.parentNode:
			print "Nodes must have same parent!"
			raise Beep
		on = 0
		selected = []
		for n in src.parentNode.childNodes:
			was_on = on
			if n is src or n is node:
				on = not was_on
			if on or was_on:
				selected.append(n)
		self.move_to(selected)
	
	def macro_pattern(self, pattern):
		"""Do the @CURRENT@ substitution for an XPath"""
		if len(self.current_nodes) != 1:
			return pattern
		node = self.get_current()
		if node.nodeType == Node.TEXT_NODE:
			current = node.data
		else:
			current = node.nodeName
		pattern = pattern.replace('@CURRENT@', current)
		#print "Searching for", pattern
		return pattern
		
	def do_search(self, pattern, ns = None, toggle = FALSE):
		if len(self.current_nodes) == 0:
			src = self.root
		else:
			src = self.current_nodes[-1]
		if not ns:
			ns = ext.GetAllNs(src)
		ns['ext'] = FT_EXT_NAMESPACE
		c = Context.Context(src, [src], processorNss = ns)
		
		rt = XPath.Evaluate(self.macro_pattern(pattern), context = c)
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
			#print "*** Search for '%s' failed" % pattern
			#print "    (namespaces were '%s')" % ns
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
		pattern = self.macro_pattern(pattern)
		return self.do_search("//text()[ext:match('%s')]" % pattern)

	def subst(self, replace, with):
		"re search and replace on the current node"
		nodes = self.current_nodes[:]
		check = len(nodes) == 1
		a = self.current_attrib
		if a:
			new = re.sub(replace, with, a.value)
			a = self.model.set_attrib(nodes[0], a.name, new)
			self.move_to(nodes[0], a)
		else:
			self.move_to([])
			final = []
			for n in nodes:
				if n.nodeType == Node.TEXT_NODE:
					old = str(n.data).replace('\n', ' ')
					new, num = re.subn(replace, with, old)
					if check and not num:
						self.move_to(n)
						raise Beep
					self.model.set_data(n, new)
					final.append(n)
				elif n.nodeType == Node.ELEMENT_NODE:
					old = str(n.nodeName)
					new, num = re.subn(replace, with, old)
					if check and not num:
						self.move_to(n)
						raise Beep
					new_ns, x = self.model.split_qname(n, new)
					final.append(self.model.set_name(n, new_ns, new))
				else:
					self.move_to(n)
					raise Beep
			self.move_to(final)

	def python(self, expr):
		"Replace node with result of expr(old_value)"
		if self.get_current().nodeType == Node.TEXT_NODE:
			vars = {'x': self.get_current().data, 're': re, 'sub': re.sub, 'string': string}
			result = eval(expr, vars)
			new = self.python_to_node(result)
			node = self.get_current()
			self.move_to([])
			self.model.replace_node(node, new)
			self.move_to(new)
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
				self.status_changed()
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
		from GetArg import GetArg
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
				c = n.cloneNode(deep)
				#print n, "->", c
				self.clipboard.appendChild(c)
		
		#print "Clip now", self.clipboard
	
	def shallow_yank(self):
		self.yank(0)
	
	def delete_shallow(self):
		nodes = self.current_nodes[:]
		if not nodes:
			return
		if self.root in nodes:
			raise Beep
		self.shallow_yank()
		self.move_to([])
		for n in nodes:
			self.model.delete_shallow(n)
		self.move_home()
	
	def delete_node_no_clipboard(self):
		self.delete_node(yank = 0)

	def delete_node(self, yank = 1):
		nodes = self.current_nodes[:]
		if not nodes:
			return
		if yank:
			self.yank()
		if self.current_attrib:
			ca = self.current_attrib
			self.current_attrib = None
			self.model.set_attrib(self.get_current(), ca.name, None)
			return
		if self.root in nodes:
			raise Beep
		self.move_to([])	# Makes things go *much* faster!
		new = []
		for x in nodes:
			p = x.parentNode
			#print "Delete %s, parent %s" % (x, p)
			if p not in new:
				new.append(p)
		self.move_to(new)
		self.model.delete_nodes(nodes)
	
	def undo(self):
		nodes = self.current_nodes[:]
		self.move_to([])
		self.model.unlock(self.root)
		try:
			self.model.undo()
		finally:
			self.model.lock(self.root)
		self.move_to(filter(lambda x: self.has_ancestor(x, self.root), nodes))

	def redo(self):
		nodes = self.current_nodes[:]
		self.move_to([])
		self.model.unlock(self.root)
		try:
			self.model.redo()
		finally:
			self.model.lock(self.root)
		self.move_to(filter(lambda x: self.has_ancestor(x, self.root), nodes))
	
	def default_done(self, exit):
		"Called when execution of a program returns. op_in_progress has been "
		"restored - move to the exit."
		#print "default_done(%s)" % exit
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
			elif exit == 'fail':
				self.jump_to_innermost_failure()
			raise Done()
	
	def jump_to_innermost_failure(self):
		assert self.innermost_failure != None

		print "Returning to innermost failure:", self.innermost_failure
		self.set_exec((self.innermost_failure, 'fail'))
		for l in self.lists:
			if hasattr(l, 'set_innermost_failure'):
				l.set_innermost_failure(self.innermost_failure)

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

			#print "Return from '%s'..." % name

			if old_ss == 2 and self.single_step == 0:
				self.single_step = old_ss
			self.callback_on_return = old_cbor

			o, exit = self.exec_point
			if op:
				#print "Resume op '%s' (%s)" % (op.program.name, op)
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
		self.status_changed()
		raise InProgress
	
	def sched(self):
		if self.op_in_progress:
			raise Exception("Operation in progress")
		if self.idle_cb:
			raise Exception("Already playing!")
		self.idle_cb = self.idle_add(self.play_callback)

	def play_callback(self):
		self.idle_remove(self.idle_cb)
		self.idle_cb = 0
		try:
			self.in_callback = 1
			try:
				self.do_one_step()
			finally:
				self.in_callback = 0
		except Done:
			(op, exit) = self.exec_point
			if exit == 'fail' and self.innermost_failure:
				self.jump_to_innermost_failure()
			print "Done, at " + time.ctime(time.time())
			self.run_new()
			return 0
		except InProgress:
			#print "InProgress"
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
			self.status_changed()
			return 0
		if self.op_in_progress or self.single_step:
			self.status_changed()
			return 0
		self.sched()
		return 0

	def status_changed(self):
		for display in self.displays:
			if hasattr(display, 'update_state'):
				display.update_state()

	def map(self, name):
		print "Map", name

		nodes = self.current_nodes[:]
		if not nodes:
			print "map of nothing: skipping..."
			return
		inp = [nodes, None]	# Nodes, next
		def next(exit = exit, self = self, name = name, inp = inp):
			"This is called while in do_one_step() - normal rules apply."
			nodes, next = inp
			print "[ %d to go ]" % len(nodes),
			if exit == 'fail':
				print "Map: nodes remaining, but an error occurred..."
				return self.default_done(exit)
			while nodes and nodes[0].parentNode == None:
				print "Skipping deleted node", nodes[0]
				del nodes[0]
			if not nodes:
				return self.default_done(exit)
			self.move_to(nodes[0])
			del nodes[0]
			if not nodes:
				next = None
			#print "Map: calling play (%d after this)" % len(nodes)
			self.play(name, done = next)	# Should raise InProgress
		if nodes is self.current_nodes:
			raise Exception("Slice failed!")
		inp[1] = next
		next('next')
	
	def name_to_prog(self, name):
		comps = string.split(name, '/')
		prog = self.model.root_program
		if prog.name != comps[0]:
			raise Exception("No such program as '%s'!" % name)
		del comps[0]
		while comps:
			prog = prog.subprograms[comps[0]]
			del comps[0]
		return prog

	def change_node(self, new_data):
		nodes = self.current_nodes
		if not nodes:
			return
		self.move_to([])
		if nodes[0].nodeType == Node.ELEMENT_NODE:
			# Slow, so do this here, even if vaguely incorrect...
			if ':' in new_data:
				(prefix, localName) = string.split(new_data, ':', 1)
			else:
				(prefix, localName) = (None, new_data)
			namespaceURI = self.model.prefix_to_namespace(nodes[0], prefix)
			out = []
			for node in nodes:
				if node is self.root:
					self.model.unlock(self.root)
					new = self.model.set_name(node, namespaceURI, new_data)
					self.model.lock(new)
					self.root = new
				else:
					new = self.model.set_name(node, namespaceURI, new_data)
				out.append(new)
			self.move_to(out)
		else:
			for node in nodes:
				self.model.set_data(node, new_data)
			self.move_to(nodes)

	def add_node(self, where, data):
		cur = self.get_current()
		if where[1] == 'e':
			if ':' in data:
				(prefix, localName) = string.split(data, ':', 1)
			else:
				(prefix, localName) = (None, data)
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

	def http_post(self):
		node = self.get_current()
		attrs = node.attributes
		post = []
		for (ns,name) in attrs.keys():
			if ns is None:
				post.append((str(name),
					     str(attrs[(ns, name)].value)))
		node = self.suck_node(node, post_data = urllib.urlencode(post))
		if node:
			self.move_to(node)
	
	def suck(self):
		nodes = self.current_nodes[:]
		attrib = self.current_attrib
		self.move_to([])
		final = []
		for x in nodes:
			try:
				new = self.suck_node(x, attrib = attrib)
			finally:
				self.move_to(x)
			final.append(new)
		self.move_to(final)
		
	def suck_node(self, node, post_data = None, attrib = None):
		uri = None
		if node.nodeType == Node.TEXT_NODE:
			uri = node.nodeValue
		else:
			if attrib:
				uri = attrib.value
			elif node.hasAttributeNS(None, 'uri'):
				uri = node.getAttributeNS(None, 'uri')
			else:
				for attr in node.attributes.keys():
					uri = node.attributes[attr].value
					if uri.find('//') != -1 or uri.find('.htm') != -1:
						break
		if not uri:
			print "Can't suck", node
			raise Beep
		if uri.find('//') == -1:
			base = self.model.get_base_uri(node)
			#print "Relative URI..."
			if base:
				#print "Base URI is:", base, "add", uri
				uri = urlparse.urljoin(base, uri)
			else:
				pass
				#print "Warning: Can't find 'uri' attribute!"

		print "Sucking", uri

		if uri.startswith('file:///'):
			assert not post_data
			stream = open(uri[7:])
			# (could read the mod time here...)
			last_mod = None
		else:
			if post_data is not None:
				print "POSTING", post_data
			stream = urllib.urlopen(uri, post_data)
			headers = stream.info().headers
			last_mod = None
			for x in headers:
				if x.lower().startswith('last-modified:'):
					last_mod = x[14:].strip()
					break
		
		current_last_mod = node.getAttributeNS(None, 'last-modified')
		if current_last_mod and last_mod:
			if current_last_mod == last_mod:
				self.model.set_attrib(node, 'modified', None)
				print "not modified => not sucking!\n"
				return

		print "Fetching page contents..."
		data = stream.read()
		print "got data... tidying..."

		(r, w) = os.pipe()
		child = os.fork()
		fixed = fix_broken_html(data)
		if child == 0:
			# We are the child
			try:
				os.close(r)
				os.dup2(w, 1)
				os.close(w)
				if fixed:
					tin = os.popen('tidy -utf8 -asxml 2>/dev/null', 'w')
				else:
					tin = os.popen('tidy -asxml 2>/dev/null', 'w')
				tin.write(fixed or data)
				tin.close()
			finally:
				os._exit(0)
		os.close(w)
		
		data = os.fdopen(r).read()
		os.waitpid(child, 0)
		
		old_md5 = node.getAttributeNS(None, 'md5_sum')
		
		import md5
		new_md5 = md5.new(data).hexdigest()
		
		if old_md5 and new_md5 == old_md5:
			self.model.set_attrib(node, 'modified', None)
			print "MD5 sums match => not parsing!"
			return
		
		reader = PyExpat.Reader()
		print "parsing...",

		from Ft.Xml.InputSource import InputSourceFactory
		from Ft.Xml.cDomlette import nonvalParse
		isrc = InputSourceFactory()

		try:
			root = nonvalParse(isrc.fromString(data, uri))
			ext.StripHtml(root)
		except:
			print "parsing failed!"
			print "Data was:"
			print data
			#support.report_exception()
			raise Beep
		else:
			print "parse OK...",
		
		new = node.ownerDocument.importNode(root.documentElement, 1)
		new.setAttributeNS(None, 'uri', uri)

		if last_mod:
			new.setAttributeNS(None, 'last-modified', last_mod)
		new.setAttributeNS(None, 'modified', 'yes')
		new.setAttributeNS(None, 'md5_sum', new_md5)

		self.move_to([])
		if node == self.root:
			self.model.unlock(self.root)
			self.model.replace_node(self.root, new)
			#self.model.strip_space(new)  (not sure we need this)
			self.model.lock(new)
			self.root = new
		else:
			self.model.replace_node(node, new)
			#self.model.strip_space(new)

		print "Loaded."
		return new
	
	def dom_from_command(self, command, callback = None, old_md5 = None):
		"""Execute shell command 'command' in the background.
		Parse the output as XML. When done, call callback(doc_root, md5).
		If old_md5 is given, compare the MD5 of the document with it,
		and do callback(None, "Same") if they match.
		"""
		#print command
		cout = os.popen(command)
	
		all = ["", None]
		def got_all(data, cb = callback, m5 = old_md5):
			import md5
			new_md5 = md5.new(data).hexdigest()
			
			if m5 and new_md5 == m5:
				cb(None, "Same")
				return
			
			reader = PyExpat.Reader()
			print "Parsing..."

			try:
				root = reader.fromStream(StringIO(data))
				ext.StripHtml(root)
			except:
				print "dom_from_command: parsing failed"
				support.report_exception()
				root = None
			cb(root, new_md5)

		# XXX: only for nogui...
		got_all(cout.read())
		return

		def got_html(src, cond, all = all, got_all = got_all):
			data = src.read(100)
			if data:
				all[0] += data
				return
			input_remove(all[1])
			src.close()
			got_all(all[0])
			
		all[1] = input_add(cout, GDK.INPUT_READ, got_html)
	
	def put_before(self):
		node = self.get_current()
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(1)
		try:
			self.model.insert_before(node, new)
		except:
			raise Beep

	def put_after(self):
		node = self.get_current()
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(1)
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
			value = value.replace('\n', ' ')
			self.model.set_attrib(node, a.name, value)
			return
		if self.clipboard.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
			if len(self.clipboard.childNodes) != 1:
				raise Beep
			new = self.clipboard.childNodes[0].cloneNode(1)
		else:
			new = self.clipboard.cloneNode(1)
		if new.nodeType != Node.ELEMENT_NODE:
			raise Beep
		self.move_to([])
		try:
			if node == self.root:
				self.model.unlock(self.root)
				try:
					self.model.replace_node(self.root, new)
					self.root = new
				finally:
					self.model.lock(self.root)
			else:
				self.model.replace_node(node, new)
			self.move_to(new)
		except:
			raise Beep

	def put_as_child(self):
		node = self.get_current()
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(1)
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
		#print "Clip now", self.clipboard
	
	def yank_attribs(self, name):
		self.clipboard = self.model.doc.createDocumentFragment()
		if name:
			if not self.get_current().hasAttribute(name):
				raise Beep
			attribs = [self.get_current().getAttributeNode(name)]
		else:
			attribs = []
			dict = self.get_current().attributes
			for a in dict.keys():
				attribs.append(dict[a])

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
		#print "Clip now", self.clipboard
	
	def paste_attribs(self):
		if self.clipboard.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
			attribs = self.clipboard.childNodes
		else:
			attribs = [self.clipboard]
		new = []
		for a in attribs:
			try:
				new.append((a.nodeName, a.childNodes[0].data))
			except:
				raise Beep
		for node in self.current_nodes:
			# XXX: Set NS attribs first...
			for (name, value) in new:
				self.model.set_attrib(node, name, value)
	
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
	
	def attribute(self, namespace = None, attrib = ''):
		node = self.get_current()

		if attrib == '':
			self.move_to(node)
			return

		if attrib == 'xmlns':
			attrib = None
		#print "(ns, attrib)", `namespace`, attrib

		a = node.attributes.get((namespace, attrib), None)

		if a:
			self.move_to(node, a)
		else:
			print "No such attribute"
			raise Beep()
	
	def set_attrib(self, value):
		a = self.current_attrib
		if not a:
			raise Beep()
		node = self.get_current()
		a = self.model.set_attrib(node, a.name, value)
		self.move_to(node, a)
	
	def add_attrib(self, UNUSED, name, value = ''):
		if name.startswith('xmlns:'):
			print "*** SET NS ATTRIB ***", self.op_in_progress.program

		node = self.get_current()
		a = self.model.set_attrib(node, name, value)
		self.move_to(node, a)
	
	def load_html(self, path):
		"Replace root with contents of this HTML file."
		print "Reading HTML..."
		command = "tidy -asxml '%s' 2>/dev/null" % path

		def done(root, md5, self = self):
			print "Loaded!"
			new = self.root.ownerDocument.importNode(root.documentElement, 1)

			if self.root:
				self.model.unlock(self.root)
			self.move_to([])
			self.model.replace_node(self.root, new)
			self.model.lock(new)
			self.root = new
			self.move_to(self.root)

		self.dom_from_command(command, done)

	def load_xml(self, path):
		"Replace root with contents of this XML (or Dome) file."
		reader = PyExpat.Reader()
		new_doc = reader.fromUri(path)
		self.load_node(new_doc.documentElement)

	def load_node(self, root):
		new = self.model.doc.importNode(root, 1)
		
		self.model.strip_space(new)

		if self.root:
			self.model.unlock(self.root)
		self.move_to([])
		self.model.replace_node(self.root, new)
		self.model.lock(new)
		self.root = new
		self.move_to(self.root)
	
	def select_dups(self):
		node = self.get_current()
		select = []
		for n in node.parentNode.childNodes:
			if n is node:
				continue
			if same(node, n):
				select.append(n)
		self.move_to(select)
	
	def select_marked_region(self, attr):
		if ':' in attr:
			(prefix, localName) = string.split(attr, ':', 1)
			namespaceURI = self.model.prefix_to_namespace(src, prefix)
		else:
			(prefix, localName) = (None, attr)
			namespaceURI = None
		select = []
		def add(node):
			if node.nodeType != Node.ELEMENT_NODE:
				return
			for key in node.attributes.keys():
				a = node.attributes[key]
				if a.localName == localName and a.namespaceURI == namespaceURI:
					select.append(node)
			map(add, node.childNodes)
		add(self.root)
		if len(select) != 2:
			print "Must be exactly two selected nodes!"
			raise Beep()
		import Path
		a = Path.path_to(select[0])
		b = Path.path_to(select[1])

		while a and b and a[0] == b[0]:
			del a[0]
			del b[0]

		if a and b:
			select = []
			s = 0
			a = a[0]
			b = b[0]
			for x in a.parentNode.childNodes:
				if x == a:
					s = 1
				elif x == b:
					s = 0
				if s:
					select.append(x)
			self.move_to(select)
		else:
			print "One node is a parent of the other!"
			raise Beep()
	
	def show_html(self):
		from HTML import HTML
		HTML(self.model, self.get_current()).show()
	
	def show_canvas(self):
		from Canvas import Canvas
		Canvas(self, self.get_current()).show()
	
	def toggle_hidden(self):
		nodes = self.current_nodes[:]
		self.move_to([])
		for node in nodes:
			if node.hasAttributeNS(None, 'hidden'):
				new = None
			else:
				new = 'yes'
			self.model.set_attrib(node, 'hidden', new, with_update = 0)
		self.model.update_all(self.root)
		self.move_to(nodes)
	
	def soap_send(self):
		copy = node_to_xml(self.get_current())
		env = copy.documentElement

		if env.namespaceURI != 'http://schemas.xmlsoap.org/soap/envelope/':
			support.report_error("Not a SOAP-ENV:Envelope (bad namespace)")
			raise Done()
		if env.localName != 'Envelope':
			support.report_error("Not a SOAP-ENV:Envelope (bad local name)")
			raise Done()

		if len(env.childNodes) != 2:
			support.report_error("SOAP-ENV:Envelope must have one header and one body")
			raise Done()

		kids = elements(env)
		head = kids[0]
		body = kids[1]

		if head.namespaceURI != 'http://schemas.xmlsoap.org/soap/envelope/' or \
		   head.localName != 'Head':
			support.report_error("First child must be a SOAP-ENV:Head element")
			raise Done()

		if body.namespaceURI != 'http://schemas.xmlsoap.org/soap/envelope/' or \
		   body.localName != 'Body':
			support.report_error("Second child must be a SOAP-ENV:Body element")
			raise Done()

		sft = None
		for header in elements(head):
			if header.namespaceURI == DOME_NS and header.localName == 'soap-forward-to':
				sft = header
				break
			print header.namespaceURI
			print header.localName

		if not sft:
			support.report_error("Head must contain a dome:soap-forward-to element")
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
			support.report_error("SOAP is only supported for 'http:' -- sorry!")
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

		new = self.model.doc.importNode(new_doc.documentElement, 1)
		
		self.model.strip_space(new)

		old = self.get_current()
		self.move_to([])
		self.model.replace_node(old, new)
		self.move_to(new)
	
	def program_changed(self, changed_op):
		print "Check points..."
		if self.rec_point:
			(op, exit) = self.rec_point
			if not op.program:
				print "Lost rec_point"
				self.rec_point = None
		if self.exec_point:
			(op, exit) = self.exec_point
			if not op.program:
				print "Lost exec_point"
				self.exec_point = None
		for l in self.lists:
			l.update_points()
		self.status_changed()
		
	def prog_tree_changed(self):
		pass
	
	def export_all(self):
		doc = implementation.createDocument(DOME_NS, 'dome', None)
		node = self.model.root_program.to_xml(doc)
		doc.documentElement.appendChild(node)
		node = doc.createElementNS(DOME_NS, 'dome-data')
		doc.documentElement.appendChild(node)

		if self.chroots:
			print "*** WARNING: Saving from a chroot!"
		model = self.model
		data = doc.importNode(model.doc.documentElement, 1)
		node.appendChild(data)

		return doc
	
	def blank_all(self):
		doc = implementation.createDocument(None, 'root', None)
		self.move_home()
		self.clipboard = self.model.doc.createElementNS(None, 'root')
		self.put_replace()

class StrGrab:
	data = ''

	def write(self, str):
		self.data += str
