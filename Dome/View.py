from gtk import *
from support import *

# An view contains:
# - A ref to a DOM document
# - A current node
# - A root node
# - A chroot stack
# It does not have any display code.

class View:
	def __init__(self, model):
		self.model = model
		self.current = model.get_root()
		self.root = self.current
		self.chroots = []
	
	def home(self):
		"Move current to the display root."
		self.move_to_node(self.root_node)
	
	def move_to_node(self, node):
		if self.current == node:
			return

		self.current = node
	
	def enter(self):
		"Change the display root to the current node."
		n = 0
		node = self.current_node
		while node != self.root:
			n += 1
			node = node.parentNode
		self.root = self.current_node
		self.chroots.append(n)
	
	def leave(self):
		"Undo the effect of the last chroot()."
		if not self.chroots:
			raise Exception('No Enter to undo!')

		n = self.chroots.pop()
		while n > 0:
			n = n - 1
			self.root = self.root.parentNode
