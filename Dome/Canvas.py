from gtk import *
from GDK import *
from gnome.ui import *

import sys
import traceback

class Canvas(GtkWindow):
	def __init__(self, view):
		GtkWindow.__init__(self)
		self.view = view

		self.canvas = GnomeCanvas()
		self.add(self.canvas)
		self.canvas.show()

		self.group = None

		s = self.canvas.get_style().copy()
		s.bg[STATE_NORMAL] = self.canvas.get_color('LemonChiffon')
		self.canvas.set_style(s)

		self.view.add_display(self)
		self.update_all()
		self.connect('destroy', self.destroyed)
	
	def destroyed(self, widget):
		print "Gone!"
		self.view.remove_display(self)
	
	def update_all(self, node = None):
		print "Update!"
		if self.group:
			self.group.destroy()
		self.group = self.build(self.canvas.root(), self.view.root)
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
				attrs[str(a.localName)] = eval(str(a.value))
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
			
		try:
			item = apply(group.add, [str(node.localName)], attrs)
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
