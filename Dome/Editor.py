from gtk import *
from GDK import *
import string

from Node import *

def edit_node(tree, node):
	if isinstance(node, DataNode):
		DataEditor(node, tree)
	else:
		NodeEditor(node, tree)

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

		button = GtkButton('OK')
		button.set_flags(CAN_DEFAULT)
		actions.pack_start(button, TRUE, TRUE, 0)
		button.grab_default(button)
		button.connect('clicked', self.ok)
		
		button = GtkButton('Cancel')
		button.set_flags(CAN_DEFAULT)
		actions.pack_start(button, TRUE, TRUE, 0)
		button.connect_object('clicked', self.destroy, self)

		self.show_all(self.vbox)

class DataEditor(Editor):
	def __init__(self, node, tree):
		Editor.__init__(self, node, tree)

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
	
class NodeEditor(Editor):
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
