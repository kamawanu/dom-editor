from gtk import *
from GDK import *
from _gtk import *

from support import *

from Node import *
from Editor import *

# Graphical tree widget

class Tree(GtkDrawingArea):
	vmargin = 4

	def __init__(self, root, vadj):
		GtkDrawingArea.__init__(self)
		TagNode('BaseRoot').add(root)
		self.vadj = vadj
		self.set_events(BUTTON_PRESS_MASK)
		self.set_flags(CAN_FOCUS)
		self.connect('expose-event', self.expose)
		self.connect('button-press-event', self.button_press)
		self.connect('key-press-event', self.key_press)
		self.root = root
		self.display_root = root
		self.current_line = 0
		self.clipboard = None
		self.left_hist = []
		self.connect('realize', self.realize)

	def key_press(self, widget, kev):
		try:
			stop = self.handle_key(kev)
		except:
			report_exception()
		if stop:
			widget.emit_stop_by_name('key-press-event')
		return stop
	
	def handle_key(self, kev):
		cur = self.line_to_node[self.current_line]
		key = kev.keyval
		new = None

		if key == F3:
			return 0
		
		if key == I or key == A or key == O:
			if not isinstance(cur, DataNode):
				new = TagNode(cur.type)
			else:
				new = TagNode(cur.parent.type)
			edit = 1
		elif key == i or key == a or key == o:
			new = DataNode('')
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
			while len(last.kids) > 0:
				last = last.kids[-1]
			self.move_to_node(last)
		elif key == Left and cur is not self.display_root:
			self.left_hist.append(self.current_line)
			self.move_to_node(cur.parent)
		elif key == Right and len(self.left_hist) > 0:
			line = self.left_hist.pop()
			node = None
			try:
				node = self.line_to_node[line]
			except IndexError:
				pass
			if node and node.parent == cur:
				self.move_to(line)
			else:
				self.left_hist = []
		elif key == Prior and cur is not self.display_root:
			self.move_to_node(cur.prev_sibling())
		elif key == Next and cur is not self.display_root:
			self.move_to_node(cur.next_sibling())
		elif key == y:
			self.clipboard = cur.copy()
		elif key == p:
			new = self.clipboard.copy()
			key = a
		elif key == bracketright:
			new = self.clipboard.copy()
			key = o
		elif key == P:
			new = self.clipboard.copy()
			key = i
		elif key == Return:
			edit_node(self, cur)
		elif key == u and cur.can_undo():
			cur.do_undo()
			new = cur
		elif key == r and cur.can_redo():
			cur.do_redo()
			new = cur
		elif key == J:
			cur.join()
			new = cur
		elif key == S and cur != self.display_root:
			cur.split(self.current_line - self.node_to_line[cur])
			new = cur.next_sibling()
		elif key == D and cur != self.display_root:
			new = cur.kids[0]
			if new:
				cur.parent.flatten(cur)
			else:
				key = x

		if new and (key == o or key == O):
			cur.add(new, index = 0)
		elif cur != self.display_root:
			if new and (key == I or key == i):
				cur.parent.add(new, before = cur)
			elif new and (key == a or key == A):
				cur.parent.add(new, after = cur)
			elif key == X:
				cur, new = cur.prev_sibling(), cur
				if cur:
					self.clipboard = cur.copy()
					cur.parent.remove(cur)
				else:
					new = None
			elif key == x:
				new = cur.next_sibling()
				if not new:
					self.move_to(self.current_line - 1)
					new = self.line_to_node[ \
							self.current_line]
				self.clipboard = cur.copy()
				cur.parent.remove(cur)
		if new and (new.parent or new == self.display_root):
			self.build_index()
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
		cn = self.line_to_node[self.current_line]
		cnp = cn.parent

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

			for x in range(0, node.get_lines()):
				self.line_to_node.append(node)
			for k in node.kids:
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

		if isinstance(node, DataNode):
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
			p = p.parent
			parents.append(p)

		x = len(parents) * 32 + 8
		if isinstance(node, DataNode):
			gdk_draw_string(self.win, self.st.font, gc,
				x, y + font.ascent,
				node.text[line - self.node_to_line[node]])
		else:
			gdk_draw_string(self.win, self.st.font, gc,
				x, y + font.ascent, str(node))

		ly = y + self.row_height / 2
		if self.node_to_line[node] == line:
			gdk_draw_line(self.win, self.st.black_gc,
						x - 24, ly, x - 4, ly)
		
		x = x - 24
		for p in parents:
			lc = self.node_to_line[p.kids[-1]]

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
