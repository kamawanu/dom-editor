from gtk import *
from GDK import *
from _gtk import *
from xml.dom.Node import Node

import string

from View import View

class Display(View, GtkDrawingArea):
	vmargin = 4

	def __init__(self, model):
		GtkDrawingArea.__init__(self)
		self.connect('expose-event', self.expose)
		self.connect('realize', self.realize)
		self.connect('destroy', self.destroyed)
		View.__init__(self, model)
	
	def update_all(self):
		View.update_all(self)
		self.build_index()
		self.force_redraw()
	
	def destroyed(self, widget):
		self.delete()
	
	def realize(self, widget):
		self.win = self.get_window()
		self.st = self.get_style()
		font = self.st.font
		self.row_height = font.ascent + font.descent
		self.build_index()

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

		off = line - self.node_to_line[self.current]
		if off >= 0 and off < self.get_lines(self.current):
			self.alloc = self.get_allocation()
			gdk_draw_rectangle(self.win,
					self.st.bg_gc[STATE_SELECTED], TRUE,
					0, y, self.alloc[2], height)
			gc = self.st.fg_gc[STATE_SELECTED]

		parents = []
		p = node
		while p != self.root:
			p = p.parentNode
			parents.append(p)

		x = len(parents) * 32 + 8
		gdk_draw_string(self.win, self.st.font, gc,
			x, y + font.ascent,
			self.get_text(node)[line - self.node_to_line[node]])

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

	def build_index(self):
		"Create node_to_line and line_to_node and resize."
		def build(self, node, build):
			self.node_to_line[node] = len(self.line_to_node)

			for x in range(0, self.get_lines(node)):
				self.line_to_node.append(node)
			for k in node.childNodes:
				build(self, k, build)
		
		self.node_to_line = {}
		self.line_to_node = []
		build(self, self.root, build)

		height = len(self.line_to_node) * self.row_height

		self.size(-1, 2 * self.vmargin + height)

	def get_text(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return string.split(string.strip(node.nodeValue), '\n')
		elif node.nodeType == Node.ELEMENT_NODE:
			ret = [node.nodeName]
			for a in node.attributes:
				ret[0] += ' ' + a.name
			return ret
		elif node.nodeName:
			return [node.nodeName]
		elif node.nodeValue:
			return ['<noname>' + node.nodeValue]
		else:
			return ['<unknown>']
	# How many lines do we need to display this node (excluding
	# children)?
	def get_lines(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return len(self.get_text(node))
		return 1

	def redraw_node(self, node):
		(x, y, w, h) = self.get_allocation()

		try:
			y = self.node_to_line[node] * self.row_height + self.vmargin
		except KeyError:
			return
		
		h = self.get_lines(node) * self.row_height

		gdk_draw_rectangle(self.win,
				self.st.bg_gc[STATE_NORMAL],
				TRUE,
				x, y, w, h)
		
		self.queue_draw()

	def force_redraw(self):
		(x, y, w, h) = self.get_allocation()

		gdk_draw_rectangle(self.win,
				self.st.bg_gc[STATE_NORMAL],
				TRUE,
				x, y, w, h)
		
		self.queue_draw()
