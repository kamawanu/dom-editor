#from gtk import *
#from GDK import *
from gtkmozembed import GtkMozEmbed

import sys
import traceback

import os
from support import *

os.environ['MOZILLA_FIVE_HOME'] = '/usr/lib/mozilla/'

# Starting Moz twice is slow and makes us crash.
# Therefore, create a dummy widget when we're first
# loaded and never let go...
dummy_html = GtkMozEmbed()

class HTML(GtkWindow):
	def __init__(self, model, node):
		GtkWindow.__init__(self)
		self.model = model
		self.display_root = node

		self.html = GtkMozEmbed()

		self.set_title(self.display_root.nodeName)
		self.model.add_view(self)
		self.connect('destroy', self.destroyed)

		self.show()
		idle_add(self.put_in)
		self.set_default_size(600, 400)
	
	def put_in(self):
		print "Add"
		self.add(self.html)
		self.html.show()
		self.update_all()

	def update_replace(self, old, new):
		if old == self.display_root:
			self.display_root = new
		self.update_all()
	
	def update_all(self, node = None):
		print "Update HTML"
		doc = node_to_html(self.display_root)
		self.output_data = ''
		ext.PrettyPrint(doc, stream = self)
		data = self.output_data
		self.output_data = ''
		uri = self.model.get_base_uri(self.display_root)
		if not uri:
			uri = 'http://localhost/'
		if uri[:7] != 'http://':
			uri = 'file://' + uri
		print "Base URI:", uri
		print "Data:", data
		self.html.render_data(data, uri, 'text/html')

		return 0
	
	def destroyed(self, widget):
		print "Gone!"
		self.model.remove_view(self)

	def write(self, text):
		self.output_data = self.output_data + text
