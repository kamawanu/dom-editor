from gtk import *
from GDK import *
from _gtk import *
import string

from xml.dom.Node import Node
from xml.dom import ext
from xml.dom import implementation
from xml.dom.ext.reader import PyExpat

import Html
from support import *
from Tree import Tree
from SaveBox import SaveBox

def strip_space(doc):
	def cb(node, cb):
		if node.nodeType == Node.TEXT_NODE:
			node.data = string.strip(node.data)
			if node.data == '':
				node.parentNode.removeChild(node)
		else:
			for k in node.childNodes[:]:
				cb(k, cb)
	cb(doc.documentElement, cb)

def html_to_xml(html):
	"Takes an HTML DOM and creates a corresponding XML DOM."
	root = implementation.createDocument('', 'root', None)
	node = root.importNode(html.documentElement, deep = 1)
	root.replaceChild(node, root.documentElement)
	return root

class Window(GtkWindow):
	def __init__(self, path = None):
		GtkWindow.__init__(self)
		self.set_default_size(gdk_screen_width() * 2 / 3,
				      gdk_screen_height() * 2 / 3)
		self.set_position(WIN_POS_CENTER)
		self.savebox = None

		swin = GtkScrolledWindow()
		self.add(swin)
		swin.set_policy(POLICY_NEVER, POLICY_ALWAYS)

		self.uri = "Document"

		if path:
			if path != '-':
				self.uri = path
			if path[-5:] == '.html':
				print "Reading HTML..."
				reader = Html.Reader()
				root = reader.fromUri(path)
				ext.StripHtml(root)
				root = html_to_xml(root)
				self.uri = self.uri[:-5] + '.xml'
			else:
				print "Reading XML..."
				reader = PyExpat.Reader()
				root = reader.fromUri(path)
				strip_space(root)
		else:
			root = implementation.createDocument('', 'root', None)

		self.tree = Tree(self, root, swin.get_vadjustment())
		self.tree.show()
		swin.add_with_viewport(self.tree)
		swin.show()
		self.tree.grab_focus()

		self.update_title()

		self.connect('key-press-event', self.key)
	
	def update_title(self):
		title = self.uri
		if self.tree.recording:
			title += ' (recording)'
		self.set_title(title)
	
	def key(self, widget, kev):
		if kev.keyval == F3:
			self.save()
		return 1
	
	def save(self):
		if self.savebox:
			self.savebox.destroy()
		if self.uri[-5:] == '.html':
			self.savebox = SaveBox(self, 'text', 'html')
		else:
			self.savebox = SaveBox(self, 'text', 'xml')
		self.savebox.show()
	
	def get_xml(self):
		self.output_data = ''
		ext.PrettyPrint(self.tree.root, stream = self)
		d = self.output_data
		self.output_data = ''
		return d
	
	def write(self, text):
		self.output_data = self.output_data + text

	def save_as(self, path):
		return send_to_file(self.get_xml(), path)

	def send_raw(self, selection_data):
		selection_data.set(selection_data.target, 8, self.get_xml())
		
	def set_uri(self, uri):
		self.uri = uri
		self.update_title()
