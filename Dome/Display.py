from rox import g, TRUE, FALSE
from gnome2 import canvas
from xml.dom import Node
from constants import *

watch_cursor = g.gdk.Cursor(g.gdk.WATCH)
no_cursor = g.gdk.Cursor(g.gdk.TCROSS)

def set_busy(widget, busy = TRUE):
	w = widget.window
	if not w:
		return
	if busy:
		w.set_cursor(watch_cursor)
	else:
		w.set_cursor(no_cursor)

def wrap(str, width):
	ret = ''
	while len(str) > width:
		i = str[:width].rfind(' ')
		if i == -1:
			i = width
		ret = ret + str[:i + 1] + '\n'
		str = str[i + 1:]
	return ret + str

cramped_indent = 16
normal_indent = 24

class Display(canvas.Canvas):
	def __init__(self, window, view):
		canvas.Canvas.__init__(self)
		self.view = None
		self.parent_window = window
		self.root_group = None
		self.update_timeout = 0
		self.update_nodes = {}			# Set of nodes to update on update_timeout
		self.current_attrib = None		# Canvas group
		self.node_to_group = {}

		self.visible = 1

		s = self.get_style().copy()
		s.bg[g.STATE_NORMAL] = g.gdk.color_parse('old lace')
		self.set_style(s)

		self.connect('size-allocate', self.size_allocate)
		self.connect('destroy', self.destroyed)
		self.connect('button-press-event', self.bg_event)

		self.set_view(view)
	
	def size_allocate(self, canvas, size):
		x, y, width, height = self.get_allocation()
		if self.visible:
			if width < 4:
				self.visible = 0
				print "hide"
		else:
			if width > 4:
				self.visible = 1
				self.update_all()
				print "show"
	
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

		#self.update_now()	# GnomeCanvas bug?
		min_x, min_y, max_x, max_y = self.root().get_bounds()
		if max_x - min_x < w:
			max_x = min_x + w
		if max_y - min_y < h:
			max_y = min_y + h
		self.set_scroll_region(min_x - m, min_y - m, max_x + m, max_y + m)
		self.root().move(0, 0) # Magic!

	def update_record_state(self):
		self.parent_window.update_title()

	def update_all(self, node = None):
		if not node:
			node = self.view.model.doc.documentElement

		if node == self.view.root:
			self.update_nodes = {node: None}
		elif node not in self.update_nodes:
			# Note: we don't eliminate duplicates (parent and child) nodes
			# here because it takes *ages*
			self.update_nodes[node] = None

		if self.update_timeout or not self.visible:
			return		# Going to update anyway...

		if self.view.running():
			self.update_timeout = g.timeout_add(2000, self.update_callback)
		else:
			self.update_timeout = g.timeout_add(10, self.update_callback)
	
	def do_update_now(self):
		# Update now, if we need to
		if self.update_timeout:
			g.timeout_remove(self.update_timeout)
			self.update_callback()
			#self.update_timeout = g.timeout_add(10, self.update_callback)
	
	def update_callback(self):
		self.update_timeout = 0
		#print "Update...", self.update_nodes
		set_busy(self)
		try:
			for node in self.update_nodes:
				root = self.view.root
				if node is not root and self.view.has_ancestor(node, root):
					# The root is OK - the change is inside...
					try:
						group = self.node_to_group[node]
						#if group.flags() & DESTROYED:
						#	print "(group destroyed)"
						#	raise Exception('Group destroyed')
					except:
						# Modified node not created yet.
						# Don't worry, updating the parent later
						# will fix it...
						print "(node missing)"
						pass
					else:
						# Can't delete all children, so create a new group
						# instead.
						parent = group.get_property('parent')
						x = group.get_property('x')
						y = group.get_property('y')
						g = parent.add(canvas.CanvasGroup, x = x, y = y)
						group.destroy()
						self.node_to_group[node] = g
						
						self.create_tree(node, g, cramped = group.cramped)
						self.auto_highlight(node, rec = 1)
						self.child_group_resized(node)
				else:
					# Need to rebuild everything...
					if self.root_group:
						self.root_group.destroy()
					self.node_to_group = {}
					self.root_group = self.root().add(canvas.CanvasGroup, x = 0, y = 0)
					group = self.root_group
					node = self.view.root
					group.connect('event', self.node_event, node)
					print "creating tree..."
					self.create_tree(node, group)
					print "highlighting..."
					self.auto_highlight(node, rec = 1)
			self.move_from()
			self.set_bounds()
			if self.view.current_nodes:
				self.scroll_to_show(self.view.current_nodes[0])
		finally:
			set_busy(self, FALSE)
			self.update_nodes = {}
		return 0
	
	def child_group_resized(self, node):
		"The group for this node has changed size. Work up the tree making room for "
		"it (and put it in the right place)."
		kids = []
		if node == self.view.root or node not in self.node_to_group:
			return
		node = node.parentNode
		if node not in self.node_to_group:
			return
		for n in node.childNodes:
			try:
				kids.append(self.node_to_group[n])
			except KeyError:
				pass
		self.position_kids(self.node_to_group[node], kids)
		self.child_group_resized(node)
	
	def auto_highlight(self, node, rec = 0):
		a = {}
		for x in self.view.current_nodes:
			a[x] = None
		cattr = self.view.current_attrib
		def do(node):
			"After creating the tree, everything is highlighted..."
			try:
				self.highlight(self.node_to_group[node], cattr == None and node in a)
			except KeyError:
				return
			if rec:
				map(do, node.childNodes)
		do(node)
	
	def destroyed(self, widget):
		self.view.remove_display(self)
	
	def create_attribs(self, attrib, group, cramped, parent):
		group.text = group.add(canvas.CanvasText, x = 0, y = -6, anchor = g.ANCHOR_NW,
					fill_color = 'grey40',
					text = "%s=%s" % (str(attrib.name), str(attrib.value)))
		group.connect('event', self.attrib_event, parent, attrib)

		#self.update_now()	# GnomeCanvas bug?
		(lx, ly, hx, hy) = group.text.get_bounds()
		group.rect = group.add(canvas.CanvasRect,
					x1 = lx - 1, y1 = ly - 1, x2 = hx + 1, y2 = hy + 1,
					fill_color = None)
		group.rect.lower_to_bottom()
	
	def create_tree(self, node, group, cramped = 0):
		if node.nodeType == Node.ELEMENT_NODE:
			hidden = node.hasAttributeNS(None, 'hidden')
		else:
			hidden = FALSE

		group.node = node
		group.cramped = cramped
		if hidden:
			c = 'red'
		elif node.nodeType == Node.TEXT_NODE:
			c = 'lightblue'
		else:
			c = 'yellow'
		group.add(canvas.CanvasEllipse, x1 = -4, y1 = -4, x2 = 4, y2 = 4,
					fill_color = c, outline_color = 'black')
		text = self.get_text(node)

		hbox = node.nodeName == 'tr'
		if cramped:
			text = wrap(text, 32)
		else:
			text = wrap(text, 1000)
		group.text = group.add(canvas.CanvasText, x = 10 , y = -6, anchor = g.ANCHOR_NW,
					fill_color = 'black', text = text)
		self.node_to_group[node] = group

		#self.update_now()	# GnomeCanvas bug?
		(lx, ly, hx, hy) = group.text.get_bounds()
		group.rect = group.add(canvas.CanvasRect,
					x1 = -8 , y1 = ly - 1, x2 = hx + 1, y2 = hy + 1,
					fill_color = 'blue')
		#group.rect.hide()

		if hbox:
			cramped = 1

		if node.nodeType == Node.ELEMENT_NODE:
			group.attrib_to_group = {}
			if not hidden:
				ax = hx + 8
				ay = 0
				if not cramped:
					l = 0
					for key in node.attributes:
						a = node.attributes[key]
						value = a.value or ''
						l += len(a.name) + len(value)
					acramped = l > 80
				else:
					acramped = cramped
				for key in node.attributes:
					a = node.attributes[key]
					gr = group.add(canvas.CanvasGroup, x = ax, y = ay)
					self.create_attribs(a, gr, cramped, node)
					#self.update_now()	# GnomeCanvas bug?
					(alx, aly, ahx, ahy) = gr.get_bounds()
					if acramped:
						ay = ahy + 8
						hy = ahy
					else:
						ax = ahx + 8
					group.attrib_to_group[a] = gr
		
		group.hy = hy
		kids = []
		if not hidden:
			for n in node.childNodes:
				gr = group.add(canvas.CanvasGroup, x = 0, y = 0)
				gr.connect('event', self.node_event, n)
				self.create_tree(n, gr, cramped)
				kids.append(gr)
		
		self.position_kids(group, kids)
		group.rect.lower_to_bottom()

	def position_kids(self, group, kids):
		if not kids:
			return

		#assert not group.flags() & DESTROYED
		#for k in kids:
		#	assert not k.flags() & DESTROYED

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

		if node.nodeName != 'tr':
			y = hy + 4
			top = None
			for gr in kids:
				gr.set(x = 0, y = 0)
				#self.update_now()	# GnomeCanvas bug?
				(lx, ly, hx, hy) = gr.get_bounds()
				y -= ly
				lowest_child = y
				gr.set(x = indent, y = y)
				if not top:
					top = y
				y = y + hy + 4
			diag = min(top, indent)

			max_segment = 16000
			points = (4, 4, diag, diag, indent, top, indent,
					min(lowest_child, top + max_segment))
			group.lines.append(group.add(canvas.CanvasLine,
					points = points, fill_color = 'black', width_pixels = 1))
			group.lines[-1].lower_to_bottom()
			while points[-1] < lowest_child:
				old_y = points[-1]
				points = (indent, old_y, indent,
					  min(old_y + max_segment, lowest_child))
				group.lines.append(group.add(canvas.CanvasLine,
					points = points, fill_color = 'black', width_pixels = 1))
				group.lines[-1].lower_to_bottom()
		else:
			y = hy + 8
			x = indent
			for gr in kids:
				gr.set(x = 0, y = 0)
				#self.update_now()	# GnomeCanvas bug?
				(lx, ly, hx, hy) = gr.get_bounds()
				x -= lx
				gr.set(x = x, y = y - ly)
				group.lines.append(group.add(canvas.CanvasLine,
						points = (x, y - 4, x, y - ly - 4),
						fill_color = 'black',
						width_pixels = 1))
				right_child = x
				x += hx - lx + 8
			group.lines.append(group.add(canvas.CanvasLine,
					points = (0, 4, 0, y - 4, right_child, y - 4),
					fill_color = 'black',
					width_pixels = 1))
			group.lines[-1].lower_to_bottom()

	def get_text(self, node):
		if node.nodeType == Node.TEXT_NODE:
			return node.nodeValue.strip()
		elif node.nodeType == Node.ELEMENT_NODE:
			return node.nodeName
		elif node.nodeType == Node.COMMENT_NODE:
			return node.nodeValue.strip()
		elif node.nodeName:
			return node.nodeName
		elif node.nodeValue:
			return '<noname>' + node.nodeValue
		else:
			return '<unknown>'
	
	def show_menu(self, bev):
		pass

	def bg_event(self, widget, event):
		if event.type == g.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu(event)
			return 1

	# 'group' and 'node' may be None (for the background)
	def node_event(self, group, event, node):
		if (event.type == g.gdk.BUTTON_PRESS or event.type == g.gdk._2BUTTON_PRESS) and event.button == 1:
			self.do_update_now()
			self.node_clicked(node, event)
			return 1
		return 0

	def attrib_event(self, group, event, element, attrib):
		if event.type != g.gdk.BUTTON_PRESS or event.button == 3:
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
					self.highlight(self.node_to_group[n], FALSE)
				except KeyError:
					pass
		if self.update_timeout or not self.visible:
			return		# We'll highlight on the callback...
		# We can update without structural problems...
		if self.view.current_nodes:
			self.scroll_to_show(self.view.current_nodes[0])
		if self.view.current_attrib:
			pass
		else:
			for n in new:
				try:
					self.highlight(self.node_to_group[n], TRUE)
				except KeyError:
					print "Warning: Node %s not in node_to_group" % n

	def set_current_attrib(self, attrib):
		"Select 'attrib' attribute node of the current node. None to unselect."
		if self.current_attrib:
			self.current_attrib.rect.set(fill_color = None)
			self.current_attrib.text.set(fill_color = 'grey40')
			self.current_attrib = None
		if attrib:
			try:
				group = self.node_to_group[self.view.get_current()].attrib_to_group[attrib]
				group.rect.set(fill_color = 'blue')
				group.text.set(fill_color = 'white')
				self.current_attrib = group
			except KeyError:
				pass
	
	def marked_changed(self, nodes):
		"nodes is a list of nodes to be rechecked."
		marked = self.view.marked
		for n in nodes:
			try:
				group = self.node_to_group[n]
				group.rect.set(outline_color = (n in marked and 'orange') or None)
			except KeyError:
				pass 	# Will regenerate later

	def highlight(self, group, state):
		node = group.node
		if state:
			group.text.set(fill_color = 'white')
			rfill = 'blue'
		else:
			rfill = None
			nt = node.nodeType
			if nt == 1: #Node.ELEMENT_NODE:
				group.text.set(fill_color = 'black')
			elif nt == 3: #Node.TEXT_NODE:
				group.text.set(fill_color = 'blue')
			elif nt == 8: #Node.COMMENT_NODE:
				group.text.set(fill_color = 'darkgreen')
			else:
				group.text.set(fill_color = 'red')
		if node in self.view.marked:
			oc = 'orange'
		else:
			oc = None
		group.rect.set(fill_color = rfill, outline_color = oc)

	def world_to_canvas(self, (x, y)):
		"Canvas routine seems to be broken..."
		mx, my, maxx, maxy = self.get_scroll_region()
		return (x - mx, y - my)
		
	def scroll_to_show(self, node):
		try:
			group = self.node_to_group[node]
		except KeyError:
			return
		#self.update_now()	# GnomeCanvas bug?
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
