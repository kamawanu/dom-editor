from __future__ import generators

import rox
from rox import g
from xml.dom import Node

def calc_node(display, node, pos):
	if node.nodeType == Node.TEXT_NODE:
		text = node.nodeValue.strip()
	elif node.nodeType == Node.ELEMENT_NODE:
		text = node.nodeName
	elif node.nodeType == Node.COMMENT_NODE:
		text = node.nodeValue.strip()
	elif node.nodeName:
		text = node.nodeName
	elif node.nodeValue:
		text = '<noname>' + node.nodeValue
	else:
		text = '<unknown>'

	layout = display.create_pango_layout(text)
	width, height = layout.get_pixel_size()
	x, y = pos

	def draw_fn():
		surface = display.pm
		fg = display.style.fg_gc
		bg = display.style.bg_gc

		surface.draw_rectangle(fg[g.STATE_NORMAL], True,
					x, y, 8, height - 1)
		surface.draw_rectangle(display.style.white_gc, True,
					x + 1, y + 1, 6, height - 3)
		
		if node in display.selection:
			surface.draw_rectangle(bg[g.STATE_SELECTED], True,
				x + 12, y, width - 1, height - 1)
			surface.draw_layout(fg[g.STATE_SELECTED], x + 12, y, layout)
		else:
			surface.draw_layout(fg[g.STATE_NORMAL], x + 12, y, layout)

	bbox = (x, y, x + 12 + width, y + height)
	return bbox, draw_fn

class Display(g.EventBox):
	def __init__(self, window, view):
		g.EventBox.__init__(self)
		self.set_app_paintable(True)
		self.set_double_buffered(False)
		self.update_timeout = 0
		
		self.view = None
		self.parent_window = window
		self.pm = None

		s = self.get_style().copy()
		s.bg[g.STATE_NORMAL] = g.gdk.color_parse('old lace')
		self.set_style(s)

		#self.connect('destroy', self.destroyed)
		self.connect('button-press-event', self.bg_event)
		self.connect('button-release-event', self.bg_event)

		#self.set_view(view)

		#rox.app_options.add_notify(self.options_changed)

		# Display is relative to this node, which is the highest displayed node (possibly
		# off the top of the screen)
		self.ref_node = view.root
		self.ref_pos = (0, 0)

		self.last_alloc = None
		self.connect('size-allocate', lambda w, a: self.size_allocate(a))
		self.connect('size-request', lambda w, r: self.size_request(r))
		self.connect('expose-event', lambda w, e: 1)

		self.pan_timeout = None
		self.set_view(view)
	
	def size_allocate(self, alloc):
		new = (alloc.width, alloc.height)
		if self.last_alloc == new:
			return
		self.last_alloc = new
		assert self.window
		#print "Alloc", alloc.width, alloc.height
		pm = g.gdk.Pixmap(self.window, alloc.width, alloc.height, -1)
		self.window.set_back_pixmap(pm, False)
		self.pm = pm
		self.update()

	def update(self):
		if not self.pm: return
		#print "update"

		self.update_timeout = 0

		self.pm.draw_rectangle(self.style.bg_gc[g.STATE_NORMAL], True,
				  0, 0, self.last_alloc[0], self.last_alloc[1])

		self.drawn = {}	# xmlNode -> (x1, y1, y2, y2)

		self.selection = {}
		for n in self.view.current_nodes:
			self.selection[n] = None

		pos = list(self.ref_pos)
		node = self.ref_node
		for node, bbox, draw_fn in self.walk_tree(self.ref_node, self.ref_pos):
			if bbox[1] > self.last_alloc[1]: break	# Off-screen
			
			draw_fn()
			self.drawn[node] = bbox
			if bbox[1] < 0:
				self.ref_node = node
				self.ref_pos = bbox[:2]

		self.window.clear()

		return 0
	
	def walk_tree(self, node, pos):
		"""Yield this (node, bbox), and all following ones in document order."""
		pos = list(pos)
		while node:
			bbox, draw_fn = calc_node(self, node, pos)
			yield (node, bbox, draw_fn)
			pos[1] = bbox[3] + 2
			if node.childNodes:
				node = node.childNodes[0]
				pos[0] += 16
			else:
				while not node.nextSibling:
					node = node.parentNode
					if not node: return
					pos[0] -= 16
				node = node.nextSibling
	
	def size_request(self, req):
		req.width = 4
		req.height = 4

	def do_update_now(self):
		# Update now, if we need to
		if self.update_timeout:
			g.timeout_remove(self.update_timeout)
			self.update()

	def update_all(self, node = None):
		if self.update_timeout:
			return		# Going to update anyway...

		if self.view.running():
			self.update_timeout = g.timeout_add(2000, self.update)
		else:
			self.update_timeout = g.timeout_add(10, self.update)
	
	def move_from(self, old = []):
		self.update_all()

	def set_view(self, view):
		if self.view:
			self.view.remove_display(self)
		self.view = view
		self.view.add_display(self)
		self.update_all()

	def show_menu(self, bev):
		pass
	
	def node_clicked(self, node, event):
		pass

	def xy_to_node(self, x, y):
		for (n, (x1, y1, x2, y2)) in self.drawn.iteritems():
			if x >= x1 and x <= x2 and y >= y1 and y <= y2:
				return n
	
	def pan(self):
		x, y, mask = self.window.get_pointer()
		sx, sy = self.pan_start
		new = [self.ref_pos[0] + (x - sx) / 8, self.ref_pos[1] + (y - sy)]
		if new == self.ref_pos:
			return 1

		self.ref_pos = new

		# Walk up the parents until we get a ref node above the start of the screen
		# (redraw will come back down)
		while self.ref_pos[1] > 0 and self.ref_node.parentNode:
			src = self.ref_node
			self.ref_node = self.ref_node.parentNode

			# Walk from the parent node to find how far it is to this node...
			for node, bbox, draw_fn in self.walk_tree(self.ref_node, (0, 0)):
				if node is src: break
			else:
				assert 0

			self.ref_pos[0] -= bbox[0]
			self.ref_pos[1] -= bbox[1]

			print "(start from %s at (%d,%d))" % (self.ref_node, self.ref_pos[0], self.ref_pos[1])

		self.update()
		
		return 1

	def bg_event(self, widget, event):
		if event.type == g.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu(event)
		elif event.type == g.gdk.BUTTON_PRESS or event.type == g.gdk._2BUTTON_PRESS:
			self.do_update_now()
			node = self.xy_to_node(event.x, event.y)
			if event.button == 1:
				if node:
					self.node_clicked(node, event)
			elif event.button == 2:
				assert self.pan_timeout is None
				self.pan_start = (event.x, event.y)
				self.pan_timeout = g.timeout_add(100, self.pan)
		elif event.type == g.gdk.BUTTON_RELEASE and event.button == 2:
			assert self.pan_timeout is not None
			g.timeout_remove(self.pan_timeout)
			self.pan_timeout = None
		else:
			return 0
		return 1

