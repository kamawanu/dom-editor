from gtk import *
from gnome.ui import *
from GDK import *
from _gtk import *
from xml.dom.Node import Node

import string
import Exec

def wrap(str, width):
	ret = ''
	while len(str) > width:
		i = string.rfind(str[:width], ' ')
		if i == -1:
			i = width
		ret = ret + str[:i + 1] + '\n'
		str = str[i + 1:]
	return ret + str

class Display(GnomeCanvas):
	def __init__(self, window, view):
		GnomeCanvas.__init__(self)
		self.view = None
		self.window = window
		self.root_group = None
		self.update_timeout = 0

		s = self.get_style().copy()
		s.bg[STATE_NORMAL] = self.get_color('old lace')
		self.set_style(s)

		self.connect('destroy', self.destroyed)
		self.connect('button-press-event', self.bg_event)

		self.set_view(view)
	
	def set_view(self, view):
		if self.view:
			self.view.remove_display(self)
		self.view = view
		self.view.add_display(self)
		self.update_all()
	
	def set_bounds(self):
		min_x, min_y, max_x, max_y = self.root().get_bounds()
		m = 8
		self.set_scroll_region(min_x - m, min_y - m, max_x + m, max_y + m)
		self.root().move(0, 0) # Magic!

		width = max_x - min_x + 50
		height = max_y - min_y + 50
		max_w = screen_width() * 3 / 4
		max_h = screen_height() * 3 / 4
		if width > max_w:
			width = max_w
		if height > max_h:
			height = max_h

	def update_record_state(self):
		self.window.update_title()

	def update_all(self):
		if self.update_timeout:
			return		# Going to update anyway...

		if Exec.exec_state.running():
			self.update_timeout = timeout_add(200, self.update_callback)
		else:
			self.update_timeout = timeout_add(10, self.update_callback)
	
	def do_update_now(self):
		# Update now, if we need to
		if self.update_timeout:
			timeout_remove(self.update_timeout)
			self.update_callback()
	
	def update_callback(self):
		self.update_timeout = 0
		print "Update..."
		if self.root_group:
			self.root_group.destroy()
		self.root_group = self.root().add('group', x = 0, y = 0)
		self.node_to_group = {}
		self.create_tree(self.view.root, self.root_group)
		self.set_bounds()
		if self.view.current_nodes:
			self.scroll_to_show(self.view.current_nodes[0])
		return 0
	
	def destroyed(self, widget):
		self.view.remove_display(self)
	
	def create_tree(self, node, group, cramped = 0):
		group.node = node
		group.add('ellipse', x1 = -4, y1 = -4, x2 = 4, y2 = 4,
					fill_color = 'yellow', outline_color = 'black')
		text = self.get_text(node)
		try:
			text = str(text)
		except UnicodeError:
			text = `text`
		if cramped:
			text = wrap(text, 32)
		group.text = group.add('text', x = 12, y = -6, anchor = ANCHOR_NW,
					font = 'fixed', fill_color = 'black',
					text = text)
		group.connect('event', self.node_event, node)
		self.node_to_group[node] = group

		(lx, ly, hx, hy) = group.text.get_bounds()
		group.rect = group.add('rect',
					x1 = lx - 1, y1 = ly - 1, x2 = hx + 1, y2 = hy + 1,
					fill_color = 'blue')
		group.rect.lower_to_bottom()
		self.hilight(group, node in self.view.current_nodes)

		hbox = node.nodeName == 'TR'
		if hbox:
			cramped = 1
		
		kids = []
		for n in node.childNodes:
			g = group.add('group', x = 0, y = 0)
			self.create_tree(n, g, cramped)
			kids.append(g)
		
		if not kids:
			return

		if cramped:
			indent = 16
		else:
			indent = 32

		if hbox:
			y = hy + 8
			x = indent
			for g in kids:
				(lx, ly, hx, hy) = g.get_bounds()
				x -= lx
				g.move(x, y - ly)
				g.add('line', points = (0, ly - 4, 0, -4),
					fill_color = 'black',
					width_pixels = 1)
				right_child = x
				x += hx - lx + 8
			group.add('line', points = (0, 4, 0, y - 4, right_child, y - 4),
					fill_color = 'black',
					width_pixels = 1)
		else:
			y = hy + 4
			for g in kids:
				(lx, ly, hx, hy) = g.get_bounds()
				y -= ly
				lowest_child = y
				g.add('line', points = (-indent, 0, -4, 0),
					fill_color = 'black',
					width_pixels = 1)
				g.move(indent, y)
				y = y + hy + 4
			group.add('line', points = (0, 4, 0, lowest_child), fill_color = 'black',
					width_pixels = 1)

	def get_text(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return string.strip(node.nodeValue)
		elif node.nodeType == Node.ELEMENT_NODE:
			ret = node.nodeName
			for a in node.attributes:
				val = a.value
				if len(val) > 21:
					val = '...' + val[-18:]
				ret += ' ' + a.name + '=' + val
			return ret
		elif node.nodeType == Node.COMMENT_NODE:
			return node.nodeValue
		elif node.nodeName:
			return node.nodeName
		elif node.nodeValue:
			return '<noname>' + node.nodeValue
		else:
			return '<unknown>'
	
	def show_menu(self, bev):
		pass

	def bg_event(self, widget, event):
		if event.type == BUTTON_PRESS and event.button == 3:
			self.show_menu(event)
			return 1

	# 'group' and 'node' may be None (for the background)
	def node_event(self, group, event, node):
		if event.type != BUTTON_PRESS or event.button == 3:
			return 0
		self.do_update_now()
		self.node_clicked(node, event)
		return 1
	
	def node_clicked(self, node):
		return
	
	def move_from(self, old):
		new = self.view.current_nodes
		for n in old:
			if n not in new:
				try:
					self.hilight(self.node_to_group[n], FALSE)
				except KeyError:
					pass
		if self.update_timeout:
			return		# We'll highlight on the callback...
		# We can update without structural problems...
		if self.view.current_nodes:
			self.scroll_to_show(self.view.current_nodes[0])
		for n in new:
			if n not in old:
				try:
					self.hilight(self.node_to_group[n], TRUE)
				except KeyError:
					pass
	
	def hilight(self, group, state):
		node = group.node
		if state:
			group.rect.show()
			group.text.set(fill_color = 'white')
		else:
			group.rect.hide()
			if node.nodeType == Node.ELEMENT_NODE:
				group.text.set(fill_color = 'black')
			elif node.nodeType == Node.TEXT_NODE:
				group.text.set(fill_color = 'blue')
			elif node.nodeType == Node.COMMENT_NODE:
				group.text.set(fill_color = 'darkgreen')
			else:
				group.text.set(fill_color = 'red')

	def scroll_to_show(self, node):
		try:
			group = self.node_to_group[node]
		except KeyError:
			return
		(lx, ly, hx, hy) = group.rect.get_bounds()
		x, y = group.i2w(0, 0)
		mx, my, maxx, maxy = self.get_scroll_region()
		x -= mx
		y -= my
		lx += x
		ly += y
		hx += x
		hy += y
		lx -= 16

		sx, sy = self.get_scroll_offsets()
		if lx < sx:
			sx = lx
		if ly < sy:
			sy = ly

		(x, y, w, h) = self.get_allocation()
		hx -= w
		hy -= h
		
		if hx > sx:
			sx = hx
		if hy > sy:
			sy = hy
		
		self.scroll_to(sx, sy)
	
	def unused():
		# Range of lines to show...
		top_line = self.node_to_line[node]
		bot_line = top_line + self.get_lines(node) - 1

		h = self.row_height
		adj = self.vadj

		min_want = top_line * h - h
		max_want = bot_line * h + 2 * h - adj.page_size
		up = adj.upper - adj.page_size

		if min_want < adj.lower:
			min_want = adj.lower
		if max_want > up:
			max_want = up
		
		if min_want < adj.value:
			adj.set_value(min_want)
		elif max_want > adj.value:
			adj.set_value(max_want)
