from gtk import *
from GDK import *
import string

import Tree

# text -> last value
history = {}

# A window which allows the user to enter a string.
# When this is done, callback(string) or callback(strings) is called.
# args is a list like ('Replace:', 'With:')

class GetArg(GtkWindow):
	def __init__(self, text, callback, args, message = None):
		GtkWindow.__init__(self, WINDOW_DIALOG)

		self.callback = callback
		self.text = text

		self.vbox = GtkVBox(FALSE, 8)
		self.add(self.vbox)
		self.set_border_width(8)
		self.set_title(text)

		if message:
			self.vbox.pack_start(GtkLabel(message), TRUE, TRUE, 0)

		self.args = []

		for a in args:
			hbox = GtkHBox(FALSE, 0)
			hbox.pack_start(GtkLabel(a), FALSE, TRUE, 0)
			arg = GtkEntry()
			hbox.pack_start(arg, TRUE, TRUE, 0)
			self.vbox.pack_start(hbox, FALSE, TRUE, 0)
			if not self.args:
				arg.grab_focus()
				arg.select_region(0, -1)
			self.args.append((a, arg))
			if len(self.args) < len(args):
				arg.connect('activate', self.to_next)
			else:
				arg.connect('activate', self.do_it)
			if history.has_key(a):
				arg.set_text(history[a])

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

	def to_next(self, widget):
		next = 0
		for (a, entry) in self.args:
			if next:
				entry.grab_focus()
				return
			if entry == widget:
				next = 1
		
	def do_it(self, widget):
		values = []
		for (a, entry) in self.args:
			val = entry.get_text()
			values.append(val)
			history[a] = val
		if len(values) > 1:
			self.callback(values)
		else:
			self.callback(values[0])
		self.destroy()
		return 1
