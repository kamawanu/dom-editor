from gtk import *
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
	
	def update_all(self, node = None):
		print "Update!"
		if self.group:
			self.group.destroy()
		self.group = self.build(self.canvas.root(), self.view.root)
	
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

		for k in node.childNodes:
			self.build(item, k)
		
		return item

	def move_from(self, old_nodes):
		pass
