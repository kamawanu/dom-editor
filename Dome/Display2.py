import rox
from rox import g
from xml.dom import Node

def init_colours(window, gc):
	global black
	black = gc

class GUINode:
	def __init__(self, widget, node):
		self.widget = widget
		self.node = node
		self.text = self.get_text(node)
		self.layout = widget.create_pango_layout(self.text)
		w, h = self.layout.get_pixel_size()
		self.text_width = w
		self.text_height = h
		self.bbox = [w + 12, max(h, 8)]
		self.kids = []
	
	def render(self, widget, x, y):
		surface = widget.pm
		fg = widget.style.fg_gc
		bg = widget.style.bg_gc
		surface.draw_rectangle(fg[g.STATE_NORMAL], True,
					x, y, 8, self.text_height - 1)
		
		if self.node in self.widget.selection:
			surface.draw_rectangle(bg[g.STATE_SELECTED], True,
				x + 12, y, self.text_width - 1, self.text_height - 1)
			surface.draw_layout(fg[g.STATE_SELECTED], x + 12, y, self.layout)
		else:
			surface.draw_layout(fg[g.STATE_NORMAL], x + 12, y, self.layout)

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
	
	def add_child(self, child):
		# Add child GUINode, and return start point for next child.
		# If child is None, return the first free point, but still update
		# space needed (for initial connector).
		if not self.kids:
			self.new_child_pos = [16, max(16, self.text_height + 2)]
			self.bbox = [max(self.bbox[0], self.new_child_pos[0]),
				     max(self.bbox[1], self.new_child_pos[1])]

		if child:
			self.bbox[1] += child.bbox[1]
			self.bbox[0] = max(self.bbox[0],
					   child.bbox[0] + self.new_child_pos[0])
			self.new_child_pos[1] += child.bbox[1]
			self.kids.append(child)
		return self.new_child_pos

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

		#self.set_view(view)

		#rox.app_options.add_notify(self.options_changed)

		# Display is relative to this node
		self.ref_node = view.root
		self.scroll_offset = (0, 0)	# 0,0 => ref node at top-left

		self.last_alloc = None
		self.connect('size-allocate', lambda w, a: self.size_allocate(a))
		self.connect('size-request', lambda w, r: self.size_request(r))
		self.connect('expose-event', lambda w, e: 1)

		self.set_view(view)
	
	def size_allocate(self, alloc):
		init_colours(self.window, self.style.black_gc)
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
		print "update"
		if self.view.current_nodes:
			self.ref_node = self.view.current_nodes[0] # XXX

		self.update_timeout = 0

		self.pm.draw_rectangle(self.style.bg_gc[g.STATE_NORMAL], True,
				  0, 0, self.last_alloc[0], self.last_alloc[1])

		self.drawn = {}	# xmlNode -> GUINode

		self.selection = {}
		for n in self.view.current_nodes:
			self.selection[n] = None
		self.add_node(self.ref_node, self.scroll_offset[0], self.scroll_offset[1])

		self.window.clear()

		return 0
	
	def size_request(self, req):
		req.width = 4
		req.height = 4
	
	def add_node(self, node, x, y):
		gn = GUINode(self, node)
		self.drawn[node] = gn
		gn.render(self, x, y)

		c = None
		for k in node.childNodes:
			cx, cy = gn.add_child(c)
			cx += x
			cy += y
			if cx > self.last_alloc[0] or cy > self.last_alloc[1]:
				return gn
			c = self.add_node(k, cx, cy)
		gn.add_child(c)
		return gn
			
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

	def bg_event(self, widget, event):
		if event.type == g.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu(event)
			return 1
