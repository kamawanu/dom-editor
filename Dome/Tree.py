from gtk import *
from GDK import *
from _gtk import *
import string
from xml.dom import Node
from xml.xpath import XPathParser, FT_EXT_NAMESPACE, Context
import types

from support import *

from Editor import edit_node
from Search import Search
import Change
from SaveBox import SaveBox
from Exec import Exec
import Macro

class Beep(Exception):
	pass

def literal_match(node):
	return "[ext:match('%s')]" % node.nodeValue

def get_text(node):
	if node.nodeType == Node.TEXT_NODE:
		return string.split(string.strip(node.nodeValue), '\n')
	elif node.nodeName:
		return [node.nodeName]
	elif node.nodeValue:
		return ['<noname>' + node.nodeValue]
	else:
		return ['<unknown>']

# Return a string that will match this node in an XPath.
def match_name(node):
	if node.nodeType == Node.TEXT_NODE:
		return 'text()'
	elif node.nodeType == Node.COMMENT_NODE:
		return 'comment()'
	else:
		return node.nodeName

def jump_to_sibling(src, dst):
	"Return an XPath which, given a context 'src' will move to sibling 'dst'."

	# Search forwards for 'dst', counting how many matching nodes we pass.
	count = 0
	check = src
	while check != dst:
		check = check.nextSibling
		if not check:
			break
		if check.nodeName == dst.nodeName:
			count += 1
	if check:
		return 'following-sibling::%s[%d]/' % (match_name(dst), count)

	# Not found - search backwards for 'dst', counting how many matching nodes we pass.
	count = 0
	check = src
	while check != dst:
		check = check.previousSibling
		if not check:
			return			# Error!
		if check.nodeName == dst.nodeName:
			count += 1
	return 'preceding-sibling::%s[%d]/' % (match_name(dst), count)

class Tree(GtkDrawingArea):
	vmargin = 4

	def __init__(self, window, root, vadj):
		GtkDrawingArea.__init__(self)
		self.window = window
		self.vadj = vadj
		self.doc = root.ownerDocument
		self.set_events(BUTTON_PRESS_MASK)
		self.set_flags(CAN_FOCUS)
		self.connect('expose-event', self.expose)
		self.connect('button-press-event', self.button_press)
		self.key_tag = window.connect('key-press-event', self.key_press)
		self.root = root
		self.display_root = root.documentElement
		self.current_line = 0
		self.clipboard = None
		self.left_hist = []
		self.connect('realize', self.realize)
		self.connect('destroy', self.destroyed)

		self.recording_where = None
		self.exec_state = Exec(self, window.macro_list)
		self.idle_tag = 0
	
	def destroyed(self, da):
		self.window.disconnect(self.key_tag)
	
	def key_press(self, widget, kev):
		try:
			stop = self.handle_key(kev)
		except:
			report_exception()
			self.build_index()
			self.current_line = 0
			self.force_redraw()
			stop = 1
			raise
		if stop:
			widget.emit_stop_by_name('key-press-event')
		return stop
	
	def handle_key(self, kev):
		key = kev.keyval

		if key == q:
			self.toggle_record()
			return 1

		if key == F3 or key == Return:
			return 0

		try:
			action = self.key_to_action[key]
		except KeyError:
			return 0

		if callable(action):
			action(self)
			return 1

		self.may_record(action)

	def toggle_record(self):
		"Start or stop recording"
		if self.recording_where:
			self.recording_where = None
		else:
			self.recording_where = self.exec_state.where

			node = self.line_to_node[self.current_line]
			if self.recording_where:
				self.recording_exit = self.exec_state.exit
			else:
				self.recording_where = \
					self.window.macro_list.record_new(node.nodeName).start
				self.recording_exit = 'next'
		
		self.window.update_title()
			
	def sched_redraw(self):
		def cb(self = self):
			self.force_redraw()
			self.move_to(self.current_line)
			self.idle_tag = 0
			return 0
		if not self.idle_tag:
			self.idle_tag = idle_add(cb)
	
	def do_action(self, action):
		"'action' is a tuple (function, arg1, arg2, ...)"
		fn = getattr(self, action[0])
		new = apply(fn, [self.line_to_node[self.current_line]] + action[1:])

		if new:
			self.build_index()
			if not self.node_to_line.has_key(new):
				new = self.display_root
			self.move_to_node(new)
			self.sched_redraw()
	
	def may_record(self, action):
		"Perform, and possibly record, this action"
		rec = self.recording_where

		try:
			self.do_action(action)
		except Beep:
			gdk_beep()
			return 0
		
		# Only record if we were recording when this action started
		if rec:
			self.recording_where = rec.record(action, self.recording_exit)
			self.recording_exit = 'next'
	
	def tree_changed(self):
		cn = self.line_to_node[self.current_line]
		cnp = cn.parentNode

		self.build_index()

		if self.node_to_line.has_key(cn):
			self.current_line = self.node_to_line[cn]
		elif self.node_to_line.has_key(cnp):
			self.current_line = self.node_to_line[cnp]
		else:
			self.current_line = 0
		self.force_redraw()
	
	def line_to_relative_path(self, line, lit):
		"Return an XPath string which will move us from current_line to line."
		"If 'lit' then the text of the (data) node must match too."
		src_node = self.line_to_node[self.current_line]
		dst_node = self.line_to_node[line]

		if src_node == dst_node:
			return '.'

		def path_to(self, node):
			"Returns a path to the node in the form [display_root, ... , node]"
			ps = [node]
			while node != self.display_root:
				node = node.parentNode
				ps.insert(0, node)
			return ps

		src_parents = path_to(self, src_node)
		dst_parents = path_to(self, dst_node)

		# Trim off all the common path elements...
		# Note that this may leave either path empty, if one node is an ancestor of the other.
		while src_parents and dst_parents and src_parents[0] == dst_parents[0]:
			del src_parents[0]
			del dst_parents[0]

		# Now, the initial context node is 'src_node'.
		# Build the path from here...
		path = ''

		# We need to go up one level for each element left in src_parents, less one
		# (so we end up as a child of the lowest common parent, on the src side).
		# If src is an ancestor of dst then this does nothing.
		# If dst is an ancestor of src then go up an extra level, because we don't jump
		# across in the next step.
		for p in range(0, len(src_parents) - 1):
			path += '../'
		if not dst_parents:
			path += '../'

		# We then jump across to the correct sibling and head back down the tree...
		# If src is an ancestor of dst or the other way round we do nothing.
		if src_parents and dst_parents:
			path += jump_to_sibling(src_parents[0], dst_parents[0])
			del dst_parents[0]

		# dst_parents is now a list of nodes to visit to get to dst.
		for node in dst_parents:
			prev = 1
			
			p = node
			while p.previousSibling:
				p = p.previousSibling
				if p.nodeName == node.nodeName:
					prev += 1
			
			path += 'child::%s[%d]/' % (match_name(node), prev)

		path = path[:-1]
		if lit:
			path += literal_match(dst_node)
		print path
		return path
	
	def button_press(self, widget, bev):
		if bev.type != BUTTON_PRESS:
			return
		if bev.button == 1:
			height = self.row_height
			line = int((bev.y - self.vmargin) / height)
			node = self.line_to_node[line]
			lit = bev.state & CONTROL_MASK
			path = self.line_to_relative_path(line, lit)
			off = line - self.node_to_line[node]
			self.may_record(["do_search", path, off])
	
	def move_to_node(self, node):
		if node:
			self.move_to(self.node_to_line[node])
	
	def move_to(self, line):
		if line < 0 or line >= len(self.line_to_node):
			return
		old_cl = self.current_line
		if line != old_cl:
			self.current_line = line
			self.force_redraw(self.current_line)
			self.force_redraw(old_cl)

		h = self.row_height
		y = line * h
		adj = self.vadj

		min_want = y - h
		max_want = y + 2 * h - adj.page_size
		up = adj.upper - adj.page_size

		if min_want < adj.lower:
			min_want = adj.lower
		if max_want > up:
			max_want = up
		
		if min_want < adj.value:
			adj.set_value(min_want)
		elif max_want > adj.value:
			adj.set_value(max_want)
	
	def realize(self, widget):
		self.win = self.get_window()
		self.st = self.get_style()
		font = self.st.font
		self.row_height = font.ascent + font.descent
		self.build_index()

	def build_index(self):
		def build(self, node, build):
			self.node_to_line[node] = len(self.line_to_node)

			for x in range(0, self.get_lines(node)):
				self.line_to_node.append(node)
			for k in node.childNodes:
				build(self, k, build)
		
		self.node_to_line = {}
		self.line_to_node = []
		build(self, self.display_root, build)

		height = len(self.line_to_node) * self.row_height

		self.size(-1, 2 * self.vmargin + height)
	
	def expose(self, da, event):
		self.level = 0
		self.y = self.vmargin
		self.x = 8

		ev_y = event.area[1] - self.vmargin

		first = ev_y / self.row_height
		last = (ev_y + event.area[3]) / self.row_height + 1

		if first < 0:
			first = 0
		if last > len(self.line_to_node) - 1:
			last = len(self.line_to_node) - 1

		while first <= last:
			self.draw_line(first)
			first = first + 1

	def draw_line(self, line):
		node = self.line_to_node[line]
		height = self.row_height
		font = self.st.font
		y = line * self.row_height + self.vmargin

		if node.nodeType != Node.ELEMENT_NODE:
			gc = self.st.fg_gc[STATE_INSENSITIVE]
		else:
			gc = self.st.fg_gc[STATE_NORMAL]

		if line == self.current_line:
			self.alloc = self.get_allocation()
			gdk_draw_rectangle(self.win,
					self.st.bg_gc[STATE_SELECTED], TRUE,
					0, y, self.alloc[2], height)
			gc = self.st.fg_gc[STATE_SELECTED]

		parents = []
		p = node
		while p != self.display_root:
			p = p.parentNode
			parents.append(p)

		x = len(parents) * 32 + 8
		gdk_draw_string(self.win, self.st.font, gc,
			x, y + font.ascent,
			get_text(node)[line - self.node_to_line[node]])

		ly = y + self.row_height / 2
		if self.node_to_line[node] == line:
			gdk_draw_line(self.win, self.st.black_gc,
						x - 24, ly, x - 4, ly)
		
		x = x - 24
		for p in parents:
			lc = self.node_to_line[p.childNodes[-1]]

			if lc > line:
				gdk_draw_line(self.win, self.st.black_gc,
					x, y, x, y + self.row_height)
			elif lc == line:
				gdk_draw_line(self.win, self.st.black_gc,
					x, y, x, y + self.row_height / 2)

			x = x - 32
	
	def force_redraw(self, line = None, height = None):
		(x, y, w, h) = self.get_allocation()

		if line != None:
			y = line * self.row_height + self.vmargin
			if height != None:
				h = height * self.row_height
			else:
				h = self.row_height

		gdk_draw_rectangle(self.win,
				self.st.bg_gc[STATE_NORMAL],
				TRUE,
				x, y, w, h)
		
		self.queue_draw()
	
	def current_node(self):
		return self.line_to_node[self.current_line]
	
	# How many lines do we need to display this node (excluding
	# children)?
	def get_lines(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return len(get_text(node))
		return 1
	
	def do_search(self, cur, pattern, off = 0):
		p = XPathParser.XPathParser()	
		path = p.parseExpression(pattern)

		ns = {'ext': FT_EXT_NAMESPACE}
		c = Context.Context(cur, [cur], processorNss = ns)
		rt = path.select(c)
		if len(rt) == 0:
			raise Beep
		node = rt[0]
		for x in rt:
			if self.node_to_line[x] > self.current_line:
				node = x
				break
		self.move_to(self.node_to_line[node] + off)

	def user_do_search(self, pattern):
		action = ["do_search", pattern]
		self.may_record(action)
		self.last_search = action

	# Motions
	def move_up(self, node):
		"Up"
		if self.current_line < 1:
			raise Beep
		self.move_to(self.current_line - 1)

	def move_down(self, node):
		"Down"
		if self.current_line + 1 >= len(self.line_to_node):
			raise Beep
		self.move_to(self.current_line + 1)

	def move_left(self, node):
		"Left"
		if node is self.display_root:
			raise Beep
		self.left_hist.append(self.current_line)
		self.move_to_node(node.parentNode)

	def move_right(self, cur):
		"Right"
 		if len(self.left_hist) == 0:
			raise Beep
		line = self.left_hist.pop()
		node = None
		try:
			node = self.line_to_node[line]
		except IndexError:
			pass
		if node and node.parentNode == cur:
			self.move_to(line)
		else:
			self.left_hist = []
			raise Beep

	def move_home(self, node):
		"Home"
		self.move_to_node(self.display_root)

	def move_end(self, node):
		"End"
		last = self.display_root
		while len(last.childNodes) > 0:
			last = last.childNodes[-1]
		self.move_to_node(last)
		
	def chroot(self, cur):
		"Chroot"
		if cur == self.display_root:
			raise Beep
		node = cur
		while node.parentNode != self.display_root:
			node = node.parentNode
		self.display_root = node
		return cur

	def unchroot(self, cur):
		"Unchroot"
		if not self.display_root.parentNode:
			raise Beep
		self.display_root = self.display_root.parentNode
		return cur
		
	def move_prev_sib(self, cur):
		"Previous sibling"
		if cur is self.display_root or not cur.previousSibling:
			raise Beep
		self.move_to_node(cur.previousSibling)

	def move_next_sib(self, cur):
		"Next sibling"
		if cur is self.display_root or not cur.nextSibling:
			raise Beep
		self.move_to_node(cur.nextSibling)

	def search(self):
		Search(self)
	
	def search_next(self, node):
		self.do_action(self.last_search)

	# Changes
	def new_element(self):
		cur = self.line_to_node[self.current_line]
		if cur.nodeType == Node.TEXT_NODE:
			return self.doc.createElement( cur.parentNode.nodeName)
		return self.doc.createElement(cur.nodeName)
	
	def insert_element(self):
		"Insert element"
		new = self.new_element()
		edit_node(self, new, "ie")
		return new

	def append_element(self):
		"Append element"
		new = self.new_element()
		edit_node(self, new, "ae")
		return new

	def open_element(self):
		"Open element"
		new = self.new_element()
		edit_node(self, new, "oe")
		
	def insert_text(self):
		"Insert text"
		new = self.doc.createTextNode('')
		edit_node(self, new, "it")

	def append_text(self):
		"Append text"
		new = self.doc.createTextNode('')
		edit_node(self, new, "at")

	def open_text(self):
		"Open text"
		new = self.doc.createTextNode('')
		edit_node(self, new, "ot")

	def yank(self, node):
		"Yank"
		self.clipboard = node.cloneNode(deep = 1)

	def put_before(self, node):
		"Put before"
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			Change.insert_before(node, new)
		except:
			raise Beep
		return new

	def put_after(self, node):
		"Put after"
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			Change.insert_after(node, new)
		except:
			raise Beep
		return new

	def put_as_child(self, node):
		"Put as child"
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		try:
			Change.insert(node, new, index = 0)
		except:
			raise Beep
		return new

	def edit_node(self):
		edit_node(self, self.line_to_node[self.current_line])

	def delete_node(self, cur):
		"Delete"
		if cur is self.display_root:
			raise Beep
		new = cur.nextSibling
		if not new:
			self.move_to(self.current_line - 1)
			new = self.line_to_node[self.current_line]
		self.clipboard = cur.cloneNode(deep = 1)
		Change.delete(cur)
		return new

	def delete_prev_sib(self, cur):
		"Delete previous sibling"
		if cur is self.display_root:
			raise Beep
		cur, new = cur.previousSibling, cur
		if not cur:
			raise Beep
		self.clipboard = cur.cloneNode(deep = 1)
		Change.delete(cur)
		return new
	
	def Start(self, node):
		pass

	def playback(self, node, macro_name):
		"Playback"
		self.exec_state.play(macro_name)

	def change_node(self, node, new_data):
		if node.nodeType == Node.TEXT_NODE:
			Change.set_data(node, new_data)
		else:
			Change.set_name(node, new_data)
		return node

	def add_node(self, node, where, data):
		cur = self.line_to_node[self.current_line]
		if where[1] == 'e':
			new = self.doc.createElement(data)
		else:
			new = self.doc.createTextNode(data)
		
		try:
			if where[0] == 'i':
				Change.insert_before(cur, new)
			elif where[0] == 'a':
				Change.insert_after(cur, new)
			else:
				Change.insert(cur, new)
		except:
			raise Beep
			
		return new

	# Undo/redo
	def undo(self, cur):
		if Change.can_undo(self.display_root):
			Change.do_undo(self.display_root)
			return cur
		else:
			raise Beep

	def redo(self, cur):
		if Change.can_redo(self.display_root):
			Change.do_redo(self.display_root)
			return cur
		else:
			raise Beep

	key_to_action = {
		# Motions
		Up	: ["move_up"],
		Down	: ["move_down"],
		Left	: ["move_left"],
		Right	: ["move_right"],
		
		Home	: ["move_home"],
		End	: ["move_end"],
		
		greater	: ["chroot"],
		less	: ["unchroot"],
		
		Prior	: ["move_prev_sib"],
		Next	: ["move_next_sib"],

		slash	: search,
		n	: ["search_next"],

		# Changes
		I	: insert_element,
		A	: append_element,
		O	: open_element,
		
		i	: insert_text,
		a	: append_text,
		o	: open_text,

		y	: ["yank"],
		P	: ["put_before"],
		p	: ["put_after"],
		bracketright : ["put_as_child"],

		Tab	: edit_node,

		x	: ["delete_node"],
		X	: ["delete_prev_sib"],

		# Undo/redo
		u	: ["undo"],
		r	: ["redo"]
	}
