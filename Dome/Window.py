from gtk import *

from xml.dom import ext
from xml.dom import implementation
from xml.dom.ext.reader import PyExpat
from xml.dom import Node

from Tree import *
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

def send_to_file(data, path):
	try:
		file = open(path, 'wb')
		try:
			file.write(data)
		finally:
			file.close()
	except:
		report_exception()
		return 0

	return 1

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
			reader = PyExpat.Reader()
			root = reader.fromUri(path)
			strip_space(root)
		else:
			root = implementation.createDocument('', 'root', None)

		self.update_title()
		
		self.tree = Tree(root, swin.get_vadjustment())
		self.tree.show()
		swin.add_with_viewport(self.tree)
		swin.show()
		self.tree.grab_focus()

		self.connect('key-press-event', self.key)
	
	def update_title(self):
		self.set_title(self.uri)
	
	def key(self, widget, kev):
		if kev.keyval == F3:
			self.save()
		return 1
	
	def save(self):
		if self.savebox:
			self.savebox.destroy()
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
