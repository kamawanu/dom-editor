from gtk import *
from GDK import *

import sys
import traceback

class Canvas(GtkWindow):
	def __init__(self, view, node):
		from gnome.ui import GnomeCanvas
		GtkWindow.__init__(self)
		self.view = view
		self.display_root = node

		self.canvas = GnomeCanvas()
		self.add(self.canvas)
		self.canvas.show()

		self.group = None

		s = self.canvas.get_style().copy()
		s.bg[STATE_NORMAL] = self.canvas.get_color('LemonChiffon')
		self.canvas.set_style(s)

		self.set_title(self.display_root.nodeName)
		self.view.add_display(self)
		self.update_all()
		self.connect('destroy', self.destroyed)
	
	def destroyed(self, widget):
		print "Gone!"
		self.view.remove_display(self)
	
	def update_all(self, node = None):
		print "Update!"
		if not self.view.has_ancestor(self.display_root, self.view.root):
			print "Display node lost - killing canvas!"
			self.destroy()
			return
		if self.group:
			self.group.destroy()
		self.group = self.build(self.canvas.root(), self.display_root)
		self.set_bounds()
	
	def set_bounds(self):
		m = 16

		min_x, min_y, max_x, max_y = self.canvas.root().get_bounds()
		min_x -= m
		min_y -= m
		max_x += m
		max_y += m
		self.canvas.set_scroll_region(min_x, min_y, max_x, max_y)
		self.canvas.root().move(0, 0) # Magic!
		self.canvas.set_usize(max_x - min_x, max_y - min_y)
	
	def build(self, group, node):
		attrs = {}
		try:
			for a in node.attributes:
				try:
					attrs[str(a.localName)] = eval(str(a.value))
				except:
					pass
		except:
			type, val, tb = sys.exc_info()
			list = traceback.extract_tb(tb)
			stack = traceback.format_list(list[-2:])
			ex = traceback.format_exception_only(type, val) + ['\n\n'] + stack
			traceback.print_exception(type, val, tb)

		if attrs.has_key('onClick'):
			onClick = attrs['onClick']
			del attrs['onClick']
		else:
			onClick = None
			
		name = str(node.localName)
		if name not in ('rect', 'line', 'text', 'ellipse'):
			name = 'group'
		try:
			item = apply(group.add, [name], attrs)
		except:
			type, val, tb = sys.exc_info()
			list = traceback.extract_tb(tb)
			stack = traceback.format_list(list[-2:])
			ex = traceback.format_exception_only(type, val) + ['\n\n'] + stack
			traceback.print_exception(type, val, tb)

			item = group.add('ellipse',
						fill_color = 'red',
						outline_color = 'black',
						x1 = -10, x2 = 10,
						y1 = -10, y2 = 10,
						width_pixels = 1)

		if onClick:
			item.connect('event', self.button_event, node, onClick)
			
		for k in node.childNodes:
			self.build(item, k)
		
		return item
	
	def button_event(self, item, event, node, prog):
		if event.type == BUTTON_PRESS and event.button == 1:
			self.view.run_new()
			self.view.move_to(node)
			self.view.do_action(['play', prog])

	def move_from(self, old_nodes):
		pass
