# An model contains:
# - A DOM document
# - The undo history
# - All macro list
# All changes to the DOM must go through here.
# Notification to views of changes is done.

from xml.dom import implementation
from xml.dom.ext.reader import PyExpat
from xml.dom import ext
from xml.dom.Node import Node
import string
import Html
import Change
from Beep import Beep

from support import html_to_xml

class Model:
	def __init__(self, macro_list):
		self.doc = implementation.createDocument('', 'root', None)
		self.views = []		# Notified when something changes
		self.macro_list = macro_list
	
	def get_root(self):
		"Return the true root node (not a view root)"
		return self.doc.documentElement
	
	def load_html(self, path):
		"Replace document with contents of this HTML file."
		print "Reading HTML..."
		reader = Html.Reader()
		root = reader.fromUri(path)
		ext.StripHtml(root)
		new = html_to_xml(self.doc, root)
		self.doc.replaceChild(new, self.doc.documentElement)
		self.update_all(self.doc)

	def load_xml(self, path):
		"Replace document with contents of this XML file."
		reader = PyExpat.Reader()
		new_doc = reader.fromUri(path)
		new = new_doc.documentElement.cloneNode(deep = 1)
		new = self.doc.importNode(new, deep = 1)
		self.doc.replaceChild(new, self.doc.documentElement)
		self.strip_space()
		self.update_all(self.doc)
	
	def add_view(self, view):
		"'view' provides:"
		"'update_all(subtree) - called when a major change occurs."
		self.views.append(view)
	
	def remove_view(self, view):
		self.views.remove(view)

	def update_all(self, node):
		"Called when 'node' has been updated."
		"'node' is still in the document, so deleting or replacing"
		"a node calls this on the parent."
		for v in self.views:
			v.update_all(node)

	def update_replace(self, old, new):
		"Called when 'old' is replaced by 'new'."
		for v in self.views:
			v.update_replace(old, new)

	def strip_space(self):
		def cb(node, cb):
			if node.nodeType == Node.TEXT_NODE:
				node.data = string.strip(node.data)
				if node.data == '':
					node.parentNode.removeChild(node)
			else:
				for k in node.childNodes[:]:
					cb(k, cb)
		cb(self.doc.documentElement, cb)

	# Changes
	
	def set_name(self, node, name):
		Change.set_name(node, name)
		self.update_all(node)
	
	def set_data(self, node, data):
		Change.set_data(node, data)
		self.update_all(node)
	
	def replace_node(self, old, new):
		Change.replace_node(old, new)
		self.update_replace(old, new)
	
	def delete_node(self, node):
		p = node.parentNode
		Change.delete(node)
		self.update_all(p)

	def undo(self, node):
		node = Change.do_undo(node)
		self.update_all(node)

	def redo(self, node):
		node = Change.do_redo(node)
		self.update_all(node)
	
	def insert(self, node, new, index = 0):
		if len(node.childNodes) > index:
			self.insert_before(node.childNodes[index], new)
		else:
			self.insert_before(None, new, parent = node)

	def insert_after(self, node, new):
		self.insert_before(node.nextSibling, new, parent = node.parentNode)

	def insert_before(self, node, new, parent = None):
		"Insert 'new' before 'node'. If 'node' is None then insert at the end"
		"of parent's children."
		if not parent:
			parent = node.parentNode
		Change.insert_before(node, new, parent)
		self.update_all(parent)
