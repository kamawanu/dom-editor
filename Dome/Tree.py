from gtk import *
from GDK import *
from _gtk import *
from xml.dom import Node

from support import *

from Editor import *
from Search import Search
import Change

# Graphical tree widget

def get_text(node, line):
	return string.split(node.nodeValue, '\n')[line]

class Tree(GtkDrawingArea):
	vmargin = 4

	def __init__(self, root, vadj):
		GtkDrawingArea.__init__(self)
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
		cur = self.line_to_node[self.current_line]
		key = kev.keyval
		new = None

		if key == F3 or key == Return:
			return 0
		
		if key == I or key == A or key == O:
			if cur.nodeType == Node.TEXT_NODE:
				new = self.doc.createElement(
						cur.parentNode.nodeName)
			else:
				new = self.doc.createElement(cur.nodeName)
			edit = 1
		elif key == i or key == a or key == o:
			new = self.doc.createTextNode('')
			edit = 1
		else:
			edit = 0

		if key == Down:
			self.move_to(self.current_line + 1)
		elif key == Up:
			self.move_to(self.current_line - 1)
		elif key == Home:
			self.move_to_node(self.display_root)
		elif key == End:
			last = self.display_root
			while len(last.childNodes) > 0:
				last = last.childNodes[-1]
			self.move_to_node(last)
		elif key == Left and cur is not self.display_root:
			self.left_hist.append(self.current_line)
			self.move_to_node(cur.parentNode)
		elif key == Right and len(self.left_hist) > 0:
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
		elif key == greater and cur != self.display_root:
			node = cur
			while node.parentNode != self.display_root:
				node = node.parentNode
			self.display_root = node
			new = cur
		elif key == less and self.display_root.parentNode:
			self.display_root = self.display_root.parentNode
			new = cur
		elif key == Prior and cur is not self.display_root:
			self.move_to_node(cur.previousSibling)
		elif key == Next and cur is not self.display_root:
			self.move_to_node(cur.nextSibling)
		elif key == y:
			self.clipboard = cur.cloneNode(deep = 1)
		elif key == p:
			new = self.clipboard.cloneNode(deep = 1)
			key = a
		elif key == bracketright:
			new = self.clipboard.cloneNode(deep = 1)
			key = o
		elif key == P:
			new = self.clipboard.cloneNode(deep = 1)
			key = i
		elif key == Tab:
			edit_node(self, cur)
		elif key == u and Change.can_undo(self.display_root):
			Change.do_undo(self.display_root)
			new = cur
		elif key == r and Change.can_redo(self.display_root):
			Change.do_redo(self.display_root)
			new = cur
#		elif key == J:
#			cur.join()
#			new = cur
#		elif key == S and cur != self.display_root:
#			cur.split(self.current_line - self.node_to_line[cur])
#			new = cur.next_sibling()
#		elif key == D and cur != self.display_root:
#			new = cur.kids[0]
#			if new:
#				cur.parent.flatten(cur)
#			else:
#				key = x
		elif key == slash:
			Search(self)

		if new and (key == o or key == O):
			Change.insert(cur, new, index = 0)
		elif cur != self.display_root:
			if new and (key == I or key == i):
				Change.insert_before(cur, new)
			elif new and (key == a or key == A):
				Change.insert_after(cur, new)
			elif key == X:
				cur, new = cur.previousSibling, cur
				if cur:
					self.clipboard = cur.cloneNode(deep = 1)
					Change.delete(cur)
				else:
					new = None
			elif key == x:
				new = cur.nextSibling
				if not new:
					self.move_to(self.current_line - 1)
					new = self.line_to_node[ \
							self.current_line]
				self.clipboard = cur.cloneNode(deep = 1)
				Change.delete(cur)
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
			if edit:
				edit_node(self, new)
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
