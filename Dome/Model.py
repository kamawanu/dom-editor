# An model contains:
# - A DOM document
# - The undo history
# All changes to the DOM must go through here.
# Notification to views of changes is done.

from xml.dom import implementation
from xml.dom.ext.reader import PyExpat
from xml.dom import ext
import Html

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
		print self.doc.documentElement

	def load_xml(self, path):
		"Replace document with contents of this XML file."
		reader = PyExpat.Reader()
		root = reader.fromUri(path)
		strip_space(root)
		self.doc.replaceChild(root, self.doc.documentElement)
