from xml.dom import XMLNS_NAMESPACE, XML_NAMESPACE

import rox
from rox import g

fixed_ns = {'xml': XML_NAMESPACE, 'xmlns': XMLNS_NAMESPACE}

class Namespaces(g.GenericTreeModel):
	def __init__(self):
		g.GenericTreeModel.__init__(self)
		self.dict = dict(fixed_ns)
		self.update_list()
	
	def update_list(self):
		self.list = self.dict.keys()
		self.list.sort()
	
	def on_get_n_columns(self):
		return 2
	
	def on_get_iter(self, path):
		assert len(path) == 1
		return path[0]
	
	def on_get_value(self, iter, column):
		if column == 0:
			return self.list[iter]
		return self.dict[self.list[iter]]
	
	def on_iter_nth_child(self, iter, n):
		if iter == None:
			return n
		return None
	
	def on_get_column_type(self, col):
		return str
	
	def on_iter_has_child(self, iter):
		return False
	
	def on_iter_next(self, iter):
		if iter < len(self.list) - 1:
			return iter + 1
	
	def __setitem__(self, prefix, uri):
		if prefix in self.dict and self.dict[prefix] == uri:
			return

		assert prefix
		assert prefix not in fixed_ns

		self.dict[prefix] = uri

class GUI(rox.Dialog):
	def __init__(self, model):
		rox.Dialog.__init__(self)
		self.model = model
		self.add_button(g.STOCK_CLOSE, g.RESPONSE_OK)
		def response(dialog, resp):
			self.destroy()
		self.connect('response', response)
		self.set_position(g.WIN_POS_MOUSE)
		self.set_title('Namespaces for ' + `model.uri`)

		tree = g.TreeView(model.namespaces)
		frame = g.Frame()
		frame.add(tree)
		frame.set_shadow_type(g.SHADOW_IN)

		cell = g.CellRendererText()
		column = g.TreeViewColumn('Prefix', cell, text = 0)
		tree.append_column(column)

		column = g.TreeViewColumn('URI', cell, text = 1)
		tree.append_column(column)
		
		frame.show_all()
		
		self.vbox.pack_start(frame, True, True)
		self.set_default_size(400, 200)

		self.set_has_separator(False)
