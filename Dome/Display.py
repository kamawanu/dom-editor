from gtk import *
from gnome.ui import *
from GDK import *
from _gtk import *
from xml.dom.Node import Node

import string

class Display(GnomeCanvas):
	def __init__(self, view):
		GnomeCanvas.__init__(self)
		self.view = None
		self.root_group = None
		self.update_idle = 0
		#self.connect('expose-event', self.expose)
		#self.connect('realize', self.realize, view)

		s = self.get_style().copy()
		s.bg[STATE_NORMAL] = self.get_color('old lace')
		self.set_style(s)

		self.connect('destroy', self.destroyed)

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

	def update_all(self):
		if self.update_idle:
			return		# Going to update anyway...
		self.update_idle = idle_add(self.update_callback)
	
	def do_update_now(self):
		# Update now, if we need to
		if self.update_idle:
			idle_remove(self.update_idle)
			self.update_callback()
	
	def update_callback(self):
		self.update_idle = 0
		print "Update..."
		if self.root_group:
			self.root_group.destroy()
		self.root_group = self.root().add('group', x = 0, y = 0)
		self.node_to_group = {}
		self.create_tree(self.view.root, self.root_group)
		self.set_bounds()
		return 0
	
	def destroyed(self, widget):
		self.view.remove_display(self)
	
	def create_tree(self, node, group):
		group.add('ellipse', x1 = -4, y1 = -4, x2 = 4, y2 = 4,
					fill_color = 'yellow', outline_color = 'black')
		group.text = group.add('text', x = 12, y = 0, anchor = ANCHOR_WEST,
					font = 'fixed', fill_color = 'black',
					text = str(string.join(self.get_text(node), '\n')))
		group.connect('event', self.node_event, node)
		self.node_to_group[node] = group

		(lx, ly, hx, hy) = group.text.get_bounds()
		group.rect = group.add('rect',
					x1 = lx - 1, y1 = ly - 1, x2 = hx + 1, y2 = hy + 1,
					fill_color = 'blue')
		group.rect.lower_to_bottom()
		self.hilight(group, node in self.view.current_nodes)

		y = hy + 4
		for n in node.childNodes:
			g = group.add('group', x = 32, y = y)
			self.create_tree(n, g)
			(lx, ly, hx, hy) = g.get_bounds()
			g.move(0, y - ly)
			y += (hy - ly) + 4

	def get_text(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return string.split(string.strip(node.nodeValue), '\n')
		elif node.nodeType == Node.ELEMENT_NODE:
			ret = [node.nodeName]
			for a in node.attributes:
				val = a.value
				if len(val) > 15:
					val = '...' + val[-12:]
				ret[0] += ' ' + a.name + '=' + val
			return ret
		elif node.nodeName:
			return [node.nodeName]
		elif node.nodeValue:
			return ['<noname>' + node.nodeValue]
		else:
			return ['<unknown>']
	
	def node_event(self, group, event, node):
		self.do_update_now()
		if event.type != BUTTON_PRESS:
			return 0
		self.node_clicked(node, event)
		return 1
	
	def node_clicked(self, node):
		return
	
	def move_from(self, old):
		self.do_update_now()
		if self.view.current_nodes:
			self.scroll_to_show(self.view.current_nodes[0])
		new = self.view.current_nodes
		for n in old:
			if n not in new:
				try:
					self.hilight(self.node_to_group[n], FALSE)
				except KeyError:
					pass
		for n in new:
			if n not in old:
				try:
					self.hilight(self.node_to_group[n], TRUE)
				except KeyError:
					pass
	
	def hilight(self, group, state):
		if state:
			group.rect.show()
			group.text.set(fill_color = 'white')
		else:
			group.rect.hide()
			group.text.set(fill_color = 'black')

	def scroll_to_show(self, node):
		pass
	
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
