from gtk import *

from loader import load_xml
from Tree import *
from SaveBox import SaveBox

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

		if path:
			self.uri = path
			root = load_xml(path)
		else:
			self.uri = "Document"
			root = TagNode('Document')

		self.update_title()
		
		tree = Tree(root, swin.get_vadjustment())
		tree.show()
		swin.add_with_viewport(tree)
		swin.show()
		tree.grab_focus()

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
		return '<?xml version="1.0"?>\n'

	def save_as(self, path):
		return send_to_file(self.get_xml(), path)

	def send_raw(self, selection_data):
		selection_data.set(selection_data.target, 8, self.get_xml())
		
	def set_uri(self, uri):
		self.uri = uri
		self.update_title()
