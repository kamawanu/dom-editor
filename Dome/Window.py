from gtk import *

from loader import load_xml
from Tree import *

class Window(GtkWindow):
	def __init__(self, path = None):
		GtkWindow.__init__(self)
		self.set_default_size(gdk_screen_width() * 2 / 3,
				      gdk_screen_height() * 2 / 3)
		self.set_position(WIN_POS_CENTER)

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
	
	def update_title(self):
		self.set_title(self.uri)
