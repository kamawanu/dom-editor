# An model contains:
# - A DOM document
# - The undo history
# All changes to the DOM must go through here.
# Notification to views of changes is done.

from xml.dom import implementation
from xml.dom.ext.reader import PyExpat
from xml.dom import ext
from xml.dom.Node import Node
import string
import Html
import Change

from support import html_to_xml

class Model:
	def __init__(self):
		self.doc = implementation.createDocument('', 'root', None)
		self.views = []		# Notified when something changes
	
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
		self.update_all()

	def load_xml(self, path):
		"Replace document with contents of this XML file."
		reader = PyExpat.Reader()
		new_doc = reader.fromUri(path)
		new = new_doc.documentElement.cloneNode(deep = 1)
		new = self.doc.importNode(new, deep = 1)
		self.doc.replaceChild(new, self.doc.documentElement)
		self.strip_space()
		self.update_all()
	
	def add_view(self, view):
		"'view' provides:"
		"'update_all() - called when a major change occurs."
		self.views.append(view)
	
	def remove_view(self, view):
		self.views.remove(view)

	def update_all(self):
		for v in self.views:
			v.update_all()

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
	
	def set_data(self, node, data):
		Change.set_data(node, data)
		self.update_all()
	
	def replace_node(self, old, new):
		Change.replace_node(old, new)
		self.update_all()
