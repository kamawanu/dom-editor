from gtk import *
from GDK import *
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
	def __init__(self, view, node):
		GtkWindow.__init__(self)
		self.view = view
		self.display_root = node

		self.html = GtkMozEmbed()

		self.set_title(self.display_root.nodeName)
		self.view.add_display(self)
		self.update_all()
		self.connect('destroy', self.destroyed)

		self.show()
		idle_add(self.put_in)
		self.set_default_size(600, 400)
	
	def put_in(self):
		print "Add"
		self.add(self.html)
		self.html.show()
		#self.html.load_url('http://localhost/')

		doc = node_to_html(self.view.root)
		self.output_data = ''
		ext.PrettyPrint(doc, stream = self)
		data = self.output_data
		self.output_data = ''
		uri = self.view.get_base_uri(self.view.root)
		if not uri:
			uri = 'http://localhost/'
		print data
		self.html.render_data(data, uri, 'text/html')

		return 0
	
	def destroyed(self, widget):
		print "Gone!"
		self.view.remove_display(self)
	
	def update_all(self, node = None):
		print "Update HTML!"
	
	def write(self, text):
		self.output_data = self.output_data + text
