#from gtk import *

class Menu:
	def __init__(self, items):
		"'items' is a list of (label, callback) tuples."
		"If callback is None then the item is shaded."
		
		menu = GtkMenu()

		for (label, callback) in items:
			item = GtkMenuItem(label)
			if callback:
				item.connect('activate', lambda widget, cb = callback: cb())
			else:
				item.set_sensitive(FALSE)
			menu.append(item)
			item.show_all()

		self.menu = menu

	def popup(self, button, time):
		self.menu.popup(None, None, None, button, time)
