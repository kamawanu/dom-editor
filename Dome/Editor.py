from gtk import *
from GDK import *
from _gtk import gdk_screen_width
import string

def edit_node(tree, node):
	if isinstance(node, DataNode):
		DataEditor(node, tree)
	elif isinstance(node, TagNode):
		TagEditor(node, tree)

class Editor(GtkWindow):
	def __init__(self, node, tree):
		GtkWindow.__init__(self, WINDOW_DIALOG)
		self.vbox = GtkVBox(FALSE, 8)
		self.add(self.vbox)
		self.tree = tree
		self.node = node
		self.set_border_width(8)

		actions = GtkHBox(TRUE, 32)
		self.vbox.pack_end(actions)

		label = GtkLabel('OK')
		label.set_padding(16, 2)
		button = GtkButton()
		button.add(label)
		button.set_flags(CAN_DEFAULT)
		actions.pack_start(button, TRUE, FALSE, 0)
		button.grab_default(button)
		button.connect('clicked', self.ok)
		
		label = GtkLabel('Cancel')
		label.set_padding(16, 2)
		button = GtkButton()
		button.add(label)
		button.set_flags(CAN_DEFAULT)
		actions.pack_start(button, TRUE, FALSE, 0)
		button.connect_object('clicked', self.destroy, self)

		self.show_all(self.vbox)

class DataEditor(Editor):
	def __init__(self, node, tree):
		Editor.__init__(self, node, tree)
		self.set_default_size(gdk_screen_width() * 2 / 3, -1)

		self.text = GtkText()
		self.text.insert_defaults(string.join(node.text, '\n'))
		self.vbox.pack_start(self.text)
		self.text.set_editable(TRUE)

		self.show_all(self.vbox)

		self.text.grab_focus()
		self.text.connect('key-press-event', self.key)
	
	def ok(self, b = None):
		self.node.set_data(self.text.get_chars(0, -1))
		self.tree.tree_changed()
		self.destroy()
	
	def key(self, text, kev):
		key = kev.keyval

		if key == Return and (kev.state & CONTROL_MASK):
			self.ok()
			return 1
		elif key == Escape:
			self.destroy()
	
class TagEditor(Editor):
	def __init__(self, node, tree):
		Editor.__init__(self, node, tree)

		self.entry = GtkEntry()
		self.entry.set_text(node.type)
		self.vbox.pack_start(self.entry)

		self.entry.grab_focus()
		self.entry.connect('activate', self.ok)
		self.entry.connect('key-press-event', self.key)
		self.entry.select_region(0, -1)

		self.show_all(self.vbox)
	
	def ok(self, widget):
		self.node.set_type(self.entry.get_text())
		self.tree.tree_changed()
		self.destroy()

	def key(self, text, kev):
		key = kev.keyval

		if key == Escape:
			self.destroy()
