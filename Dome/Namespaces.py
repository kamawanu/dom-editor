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
	
	def add_new(self):
		x = 1
		while ('ns%d' % x) in self.dict: x += 1
		self['ns%d' % x] = 'http://example.com'
	
	def __setitem__(self, prefix, uri):
		if prefix in self.dict and self.dict[prefix] == uri:
			return

		assert prefix
		assert prefix not in fixed_ns

		self.dict[prefix] = uri
		self.update_list()
		path = (self.list.index(prefix),)
		self.emit('row-inserted', path, self.get_iter(path))
	
	def __delitem__(self, iter):
		prefix = self[iter][0]
		if prefix in fixed_ns:
			raise Exception('This is a built-in namespace and cannot be deleted')
		path = (self.list.index(prefix),)
		del self.dict[prefix]
		self.update_list()
		self.emit('row-deleted', path)

class GUI(rox.Dialog):
	def __init__(self, model):
		rox.Dialog.__init__(self)
		self.model = model

		self.add_button(g.STOCK_ADD, 1)
		self.add_button(g.STOCK_DELETE, 2)
		self.add_button(g.STOCK_CLOSE, g.RESPONSE_OK)
		
		tree = g.TreeView(model.namespaces)

		def response(dialog, resp):
			if resp == 1:
				model.namespaces.add_new()
			elif resp == 2:
				self.delete_selected(tree.get_selection())
			else:
				self.destroy()
		self.connect('response', response)
		self.set_position(g.WIN_POS_MOUSE)
		self.set_title('Namespaces for ' + `model.uri`)

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
	
	def delete_selected(self, sel):
		model, iter = sel.get_selected()
		if not iter:
			rox.alert('Select a namespace binding to delete')
			return
		try:
			del model[iter]
		except:
			rox.report_exception()
