from gtk import *
from GDK import *
import string

import Tree

# text -> last value
history = {}

# A window which allows the user to enter a string.
# When this is done, callback(string) is called.

class GetArg(GtkWindow):
	def __init__(self, text, callback, message = None):
		GtkWindow.__init__(self, WINDOW_DIALOG)

		self.callback = callback
		self.text = text

		self.vbox = GtkVBox(FALSE, 8)
		self.add(self.vbox)
		self.set_border_width(8)
		self.set_title(text)

		if message:
			self.vbox.pack_start(GtkLabel(message), TRUE, TRUE, 0)

		self.pattern = GtkEntry()
		self.vbox.pack_start(self.pattern, FALSE, TRUE, 0)
		self.pattern.grab_focus()

		if history.has_key(text):
			self.pattern.set_text(history[text])
		self.pattern.select_region(0, -1)
		self.pattern.connect('activate', self.do_it)

		actions = GtkHBox(TRUE, 32)
		self.vbox.pack_end(actions, FALSE, TRUE, 0)

		label = GtkLabel('OK')
		label.set_padding(16, 2)
		button = GtkButton()
		button.add(label)
		button.set_flags(CAN_DEFAULT)
		actions.pack_start(button, TRUE, FALSE, 0)
		button.grab_default(button)
		button.connect('clicked', self.do_it)
		
		label = GtkLabel('Cancel')
		label.set_padding(16, 2)
		button = GtkButton()
		button.add(label)
		button.set_flags(CAN_DEFAULT)
		actions.pack_start(button, TRUE, FALSE, 0)
		button.connect_object('clicked', self.destroy, self)

		self.connect('key-press-event', self.key)

		self.show_all(self.vbox)
	
	def key(self, widget, kev):
		if kev.keyval == Escape:
			self.destroy()

	def do_it(self, widget):
		value = self.pattern.get_text()
		history[self.text] = value
		self.callback(value)
		self.destroy()
		return 1
