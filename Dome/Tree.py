from gtk import *
from GDK import *
from _gtk import *
from xml.dom import Node

from support import *

from Editor import *
from Search import Search
import Change

# Graphical tree widget

class Beep(Exception):
	pass

def get_text(node, line):
	return string.split(node.nodeValue, '\n')[line]

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
		self.connect('key-press-event', self.key_press)
		self.root = root
		self.display_root = root.documentElement
		self.current_line = 0
		self.clipboard = None
		self.left_hist = []
		self.connect('realize', self.realize)
		self.recording = None

	def key_press(self, widget, kev):
		try:
			stop = self.handle_key(kev)
		except:
			report_exception()
			self.build_index()
			self.current_line = 0
			self.force_redraw()
			stop = 1
		if stop:
			widget.emit_stop_by_name('key-press-event')
		return stop
	
	def handle_key(self, kev):
		key = kev.keyval

		if key == q:
			if self.recording != None:
				self.create_macro()
			else:
				self.recording = []
				self.window.update_title()
			return 1

		if key == F3 or key == Return:
			return 0

		try:
			action = self.key_to_action[key]
		except KeyError:
			return 0

		try:
			new = action(self, self.line_to_node[self.current_line])
		except Beep:
			gdk_beep()
			return 1
		
		if self.recording != None:
			self.recording.append(action)
			print "Recorded:", action.__doc__
			
		if new:
			self.build_index()
			if not self.node_to_line.has_key(new):
				new = self.display_root
			def cb(self = self, new = new):
				self.move_to_node(new)
				return 0
			self.move_to_node(new)
			idle_add(cb)
			self.force_redraw()
		return 1
	
	def tree_changed(self):
		if not self.display_root.parentNode:
			self.display_root = \
				self.display_root.ownerDocument.documentElement
		
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
	
	def button_press(self, widget, bev):
		if bev.type != BUTTON_PRESS:
			return
		if bev.button == 1:
			height = self.row_height
			line = int((bev.y - self.vmargin) / height)
			node = self.move_to(line)
	
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

		if node.nodeType == Node.TEXT_NODE:
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
		if node.nodeType == Node.TEXT_NODE:
			gdk_draw_string(self.win, self.st.font, gc,
				x, y + font.ascent,
				get_text(node, line - self.node_to_line[node]))
		else:
			gdk_draw_string(self.win, self.st.font, gc,
				x, y + font.ascent, node.nodeName)

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
			return len(string.split(node.nodeValue, '\n'))
		return 1
	
	def create_macro(self):
		self.recording = None
		self.window.update_title()

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

	def search(self, node):
		"Search"
		Search(self)

	# Changes
	def new_element(self, cur):
		if cur.nodeType == Node.TEXT_NODE:
			return self.doc.createElement( cur.parentNode.nodeName)
		return self.doc.createElement(cur.nodeName)
	
	def insert_element(self, node):
		"Insert element"
		new = self.new_element(node)
		Change.insert_before(node, new)
		edit_node(self, new)
		return new

	def append_element(self, node):
		"Append element"
		new = self.new_element(node)
		Change.insert_after(node, new)
		edit_node(self, new)
		return new

	def open_element(self, node):
		"Open element"
		new = self.new_element(node)
		Change.insert(node, new, index = 0)
		edit_node(self, new)
		return new
		
	def insert_text(self, node):
		"Insert text"
		new = self.doc.createTextNode('')
		Change.insert_before(node, new)
		edit_node(self, new)
		return new

	def append_text(self, node):
		"Append text"
		new = self.doc.createTextNode('')
		Change.insert_after(node, new)
		edit_node(self, new)
		return new

	def open_text(self, node):
		"Open text"
		new = self.doc.createTextNode('')
		Change.insert(node, new, index = 0)
		edit_node(self, new)
		return new

	def yank(self, node):
		"Yank"
		self.clipboard = node.cloneNode(deep = 1)

	def put_before(self, node):
		"Put before"
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		Change.insert_before(node, new)
		return new

	def put_after(self, node):
		"Put after"
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		Change.insert_after(node, new)
		return new

	def put_as_child(self, node):
		"Put as child"
		if self.clipboard == None:
			raise Beep
		new = self.clipboard.cloneNode(deep = 1)
		Change.insert(node, new, index = 0)
		return new

	def edit_node(self, node):
		"Edit node"
		edit_node(self, node)

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
		Up	: move_up,
		Down	: move_down,
		Left	: move_left,
		Right	: move_right,
		
		Home	: move_home,
		End	: move_end,
		
		greater	: chroot,
		less	: unchroot,
		
		Prior	: move_prev_sib,
		Next	: move_next_sib,

		slash	: search,

		# Changes
		I	: insert_element,
		A	: append_element,
		O	: open_element,
		
		i	: insert_text,
		a	: append_text,
		o	: open_text,

		y	: yank,
		P	: put_before,
		p	: put_after,
		bracketright : put_as_child,

		Tab	: edit_node,

		x	: delete_node,
		X	: delete_prev_sib,

		# Undo/redo
		u	: undo,
		r	: redo
	}
