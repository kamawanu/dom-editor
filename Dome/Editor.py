from gtk import *
from GDK import *
from _gtk import gdk_screen_width
from xml.dom.Node import Node
import string

import Change

def edit_node(tree, node, where = None):
	if node.nodeType == Node.TEXT_NODE:
		DataEditor(node, tree, where)
	elif node.nodeType == Node.ELEMENT_NODE:
		TagEditor(node, tree, where)

class Editor(GtkWindow):
	# If where is given then the action add_node(where) is recorded.
	def __init__(self, node, tree, where):
		GtkWindow.__init__(self, WINDOW_DIALOG)
		self.vbox = GtkVBox(FALSE, 8)
		self.add(self.vbox)
		self.tree = tree
		self.node = node
		self.where = where
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
	
	def do_it(self, data):
		if self.where:
			self.tree.may_record(['add_node', self.where, data])
		else:
			self.tree.may_record(['change_node', data])
		self.destroy()

class DataEditor(Editor):
	def __init__(self, node, tree, where):
		Editor.__init__(self, node, tree, where)
		self.set_default_size(gdk_screen_width() * 2 / 3, -1)

		self.text = GtkText()
		self.text.insert_defaults(node.nodeValue)
		self.vbox.pack_start(self.text)
		self.text.set_editable(TRUE)

		self.show_all(self.vbox)

		self.text.grab_focus()
		self.text.connect('key-press-event', self.key)
	
	def ok(self, b = None):
		self.do_it(self.text.get_chars(0, -1))
	
	def key(self, text, kev):
		key = kev.keyval

		if key == Return and (kev.state & CONTROL_MASK):
			self.ok()
			return 1
		elif key == Escape:
			self.destroy()
	
class TagEditor(Editor):
	def __init__(self, node, tree, where):
		Editor.__init__(self, node, tree, where)

		self.entry = GtkEntry()
		self.entry.set_text(node.nodeName)
		self.vbox.pack_start(self.entry)

		self.entry.grab_focus()
		self.entry.connect('activate', self.ok)
		self.entry.connect('key-press-event', self.key)
		self.entry.select_region(0, -1)

		self.show_all(self.vbox)
	
	def ok(self, widget):
		self.do_it(self.entry.get_text())

	def key(self, text, kev):
		key = kev.keyval

		if key == Escape:
			self.destroy()
