import rox
from rox import g, TRUE, FALSE

# text -> last value
history = {}

# A window which allows the user to enter a string.
# When this is done, callback(string) or callback(strings) is called.
# args is a list like ('Replace:', 'With:')
# If 'destroy_return' is true then closing the window does callback(None).

class GetArg(rox.Dialog):
	def __init__(self, text, callback, args, message = None,
		     destroy_return = 0, init = None):
		rox.Dialog.__init__(self)

		if init:
			init = init[:]

		self.callback = callback
		self.text = text

		self.set_title(text)

		if message:
			self.vbox.pack_start(g.Label(message), TRUE, TRUE, 0)

		self.args = []

		for a in args:
			hbox = g.HBox(FALSE, 4)
			hbox.pack_start(g.Label(a), FALSE, TRUE, 0)
			arg = g.Entry()
			hbox.pack_start(arg, TRUE, TRUE, 0)
			self.vbox.pack_start(hbox, FALSE, TRUE, 0)
			if init and init[0]:
				arg.set_text(init[0])
				del init[0]
			if history.has_key(a):
				arg.set_text(history[a])
			if not self.args:
				arg.grab_focus()
				arg.select_region(0, -1)
			self.args.append((a, arg))
			if len(self.args) < len(args):
				arg.connect('activate', self.to_next)
			else:
				arg.connect('activate', lambda w: self.do_it())

		actions = g.HBox(TRUE, 32)
		self.vbox.pack_end(actions, FALSE, TRUE, 0)

		self.add_button(g.STOCK_CANCEL, g.RESPONSE_CANCEL)
		self.add_button(g.STOCK_OK, g.RESPONSE_OK)

		def resp(widget, resp):
			if resp == g.RESPONSE_OK:
				self.do_it()
			widget.destroy()
		self.connect('response', resp)

		if destroy_return:
			self.connect('destroy', lambda widget, cb = callback: cb(None))

		self.show_all()
	
	def to_next(self, widget):
		next = 0
		for (a, entry) in self.args:
			if next:
				entry.grab_focus()
				entry.select_region(0, -1)
				return
			if entry == widget:
				next = 1
		
	def do_it(self):
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
