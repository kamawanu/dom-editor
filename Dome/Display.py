from gtk import *
from gnome.ui import *
from GDK import *
from _gtk import *
from xml.dom import Node

import string
import Exec

watch_cursor = cursor_new(WATCH)
no_cursor = cursor_new(TCROSS)

def set_busy(widget, busy = TRUE):
	if busy:
		widget.get_window().set_cursor(watch_cursor)
	else:
		widget.get_window().set_cursor(no_cursor)

def wrap(str, width):
	ret = ''
	while len(str) > width:
		i = string.rfind(str[:width], ' ')
		if i == -1:
			i = width
		ret = ret + str[:i + 1] + '\n'
		str = str[i + 1:]
	return ret + str

cramped_indent = 16
normal_indent = 24

class Display(GnomeCanvas):
	def __init__(self, window, view):
		GnomeCanvas.__init__(self)
		self.view = None
		self.window = window
		self.root_group = None
		self.update_timeout = 0
		self.update_nodes = []			# List of nodes to update on update_timeout
		self.current_attrib = None		# Canvas group
		self.node_to_group = {}

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
		m = 8

		(x, y, w, h) = self.get_allocation()
		w -= m * 2 + 1
		h -= m * 2 + 1

		min_x, min_y, max_x, max_y = self.root().get_bounds()
		if max_x - min_x < w:
			max_x = min_x + w
		if max_y - min_y < h:
			max_y = min_y + h
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

	def update_all(self, node = None):
		if not node:
			node = self.view.model.doc

		if node not in self.update_nodes:
			for n in self.update_nodes[:]:
				if self.view.has_ancestor(node, n):
					return		# Going to update the parent...
				if self.view.has_ancestor(n, node):
					self.update_nodes.remove(n)
			self.update_nodes.append(node)

		if self.update_timeout:
			return		# Going to update anyway...

		if Exec.exec_state.running():
			self.update_timeout = timeout_add(1000, self.update_callback)
		else:
			self.update_timeout = timeout_add(10, self.update_callback)
	
	def do_update_now(self):
		# Update now, if we need to
		if self.update_timeout:
			timeout_remove(self.update_timeout)
			self.update_callback()
	
	def update_callback(self):
		self.update_timeout = 0
		print "Update...", self.update_nodes
		set_busy(self)
		try:
			#XXX: self.node_to_group = {}
			for node in self.update_nodes:
				root = self.view.root
				if node is not root and self.view.has_ancestor(node, root):
					# The root is OK - the change is inside...
					group = self.node_to_group[node]
					for i in group.children():
						i.destroy()
					self.create_tree(node, group, cramped = group.cramped)
					self.auto_highlight_rec(node)
					self.child_group_resized(node)
				else:
					# Need to rebuild everything...
					if self.root_group:
						self.root_group.destroy()
					self.root_group = self.root().add('group', x = 0, y = 0)
					group = self.root_group
					node = self.view.root
					group.connect('event', self.node_event, node)
					self.create_tree(node, group)
					self.auto_highlight_rec(node)
			self.move_from()
			self.set_bounds()
			if self.view.current_nodes:
				self.scroll_to_show(self.view.current_nodes[0])
		finally:
			set_busy(self, FALSE)
			self.update_nodes = []
		return 0
	
	def child_group_resized(self, node):
		"The group for this node has changed size. Work up the tree making room for "
		"it (and put it in the right place)."
		kids = []
		if node == self.view.root:
			return
		node = node.parentNode
		for n in node.childNodes:
			kids.append(self.node_to_group[n])
		self.position_kids(self.node_to_group[node], kids)
		self.child_group_resized(node)
	
	def auto_highlight_rec(self, node):
		"After creating the tree, everything is highlighted..."
		self.auto_hightlight(node)
		for k in node.childNodes:
			self.auto_highlight_rec(k)
	
	def auto_hightlight(self, node):
		"Highlight this node depending on its selected state."
		self.hightlight(self.node_to_group[node],
			self.view.current_attrib == None and node in self.view.current_nodes)
	
	def destroyed(self, widget):
		self.view.remove_display(self)
	
	def create_attribs(self, attrib, group, cramped, parent):
		group.text = group.add('text', x = 0, y = -6, anchor = ANCHOR_NW,
					font = 'fixed', fill_color = 'grey40',
					text = "%s=%s" % (str(attrib.name), str(attrib.value)))
		group.connect('event', self.attrib_event, parent, attrib)

		(lx, ly, hx, hy) = group.text.get_bounds()
		group.rect = group.add('rect',
					x1 = lx - 1, y1 = ly - 1, x2 = hx + 1, y2 = hy + 1,
					fill_color = 'blue')
		group.rect.lower_to_bottom()
		group.rect.hide()
	
	def create_tree(self, node, group, cramped = 0):
		group.node = node
		group.cramped = cramped
		if node.nodeType == Node.TEXT_NODE:
			c = 'lightblue'
		else:
			c = 'yellow'
		group.add('ellipse', x1 = -4, y1 = -4, x2 = 4, y2 = 4,
					fill_color = c, outline_color = 'black')
		text = self.get_text(node)
		try:
			text = str(text)
		except UnicodeError:
			text = '!' + `text`

		hbox = node.nodeName == 'TR'
		if cramped:
			text = wrap(text, 32)
		group.text = group.add('text', x = 10 , y = -6, anchor = ANCHOR_NW,
					font = 'fixed', fill_color = 'black',
					text = text)
		self.node_to_group[node] = group

		(lx, ly, hx, hy) = group.text.get_bounds()
		group.rect = group.add('rect',
					x1 = -8 , y1 = ly - 1, x2 = hx + 1, y2 = hy + 1,
					fill_color = 'blue')
		group.rect.hide()

		if hbox:
			cramped = 1

		if node.nodeType == Node.ELEMENT_NODE:
			ax = hx + 8
			ay = 0
			group.attrib_to_group = {}
			if not cramped:
				l = 0
				for a in node.attributes:
					l += len(str(a.name)) + len(str(a.value))
				acramped = l > 80
			else:
				acramped = cramped
			for a in node.attributes:
				g = group.add('group', x = ax, y = ay)
				self.create_attribs(a, g, cramped, node)
				(alx, aly, ahx, ahy) = g.get_bounds()
				if acramped:
					ay = ahy + 8
					hy = ahy
				else:
					ax = ahx + 8
				group.attrib_to_group[a] = g
		
		group.hy = hy
		kids = []
		for n in node.childNodes:
			g = group.add('group', x = 0, y = 0)
			g.connect('event', self.node_event, n)
			self.create_tree(n, g, cramped)
			kids.append(g)
		
		self.position_kids(group, kids)
		group.rect.lower_to_bottom()

	def position_kids(self, group, kids):
		if not kids:
			return

		if group.cramped:
			indent = cramped_indent
		else:
			indent = normal_indent

		node = group.node
		hy = group.hy

		if hasattr(group, 'lines'):
			for l in group.lines:
				l.destroy()
		group.lines = []

		if node.nodeName == 'TR':
			y = hy + 8
			x = indent
			for g in kids:
				g.set(x = 0, y = 0)
				(lx, ly, hx, hy) = g.get_bounds()
				x -= lx
				g.set(x = x, y = y - ly)
				group.lines.append(group.add('line',
						points = (x, y - 4, x, y - ly - 4),
						fill_color = 'black',
						width_pixels = 1))
				right_child = x
				x += hx - lx + 8
			group.lines.append(group.add('line',
					points = (0, 4, 0, y - 4, right_child, y - 4),
					fill_color = 'black',
					width_pixels = 1))
			group.lines[-1].lower_to_bottom()
		else:
			y = hy + 4
			top = None
			for g in kids:
				g.set(x = 0, y = 0)
				(lx, ly, hx, hy) = g.get_bounds()
				y -= ly
				lowest_child = y
				g.set(x = indent, y = y)
				if not top:
					top = y
				y = y + hy + 4
			diag = min(top, indent)
			group.lines.append(group.add('line',
					points = (4, 4, diag, diag, indent, top, indent, lowest_child),
					fill_color = 'black', width_pixels = 1))
			group.lines[-1].lower_to_bottom()


	def get_text(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return string.strip(node.nodeValue)
		elif node.nodeType == Node.ELEMENT_NODE:
			return node.nodeName
		elif node.nodeType == Node.COMMENT_NODE:
			return string.strip(node.nodeValue)
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

	def attrib_event(self, group, event, element, attrib):
		if event.type != BUTTON_PRESS or event.button == 3:
			return 0
		self.do_update_now()
		self.attrib_clicked(element, attrib, event)
		return 1
	
	def node_clicked(self, node, event):
		return
	
	def attrib_clicked(self, element, attrib, event):
		return
	
	def move_from(self, old = []):
		self.set_current_attrib(self.view.current_attrib)

		new = self.view.current_nodes
		for n in old:
			if self.view.current_attrib or n not in new:
				try:
					self.hightlight(self.node_to_group[n], FALSE)
				except KeyError:
					pass
		if self.update_timeout:
			return		# We'll highlight on the callback...
		# We can update without structural problems...
		if self.view.current_nodes:
			self.scroll_to_show(self.view.current_nodes[0])
		if self.view.current_attrib:
			pass
		else:
			for n in new:
				try:
					self.hightlight(self.node_to_group[n], TRUE)
				except KeyError:
					print "Warning: Node %s not in node_to_group" % n

	def set_current_attrib(self, attrib):
		"Select 'attrib' attribute node of the current node. None to unselect."
		if self.current_attrib:
			self.current_attrib.rect.hide()
			self.current_attrib.text.set(fill_color = 'grey40')
			self.current_attrib = None
		if attrib:
			try:
				group = self.node_to_group[self.view.current].attrib_to_group[attrib]
				group.rect.show()
				group.text.set(fill_color = 'white')
				self.current_attrib = group
			except KeyError:
				pass

	def hightlight(self, group, state):
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

	def world_to_canvas(self, (x, y)):
		"Canvas routine seems to be broken..."
		mx, my, maxx, maxy = self.get_scroll_region()
		return (x - mx, y - my)
		
	def scroll_to_show(self, node):
		try:
			group = self.node_to_group[node]
		except KeyError:
			return
		(lx, ly, hx, hy) = group.rect.get_bounds()
		x, y = self.world_to_canvas(group.i2w(0, 0))
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
