from xml.dom import XMLNS_NAMESPACE, XML_NAMESPACE
from constants import DOME_NS
from Ft.Xml.XPath import FT_EXT_NAMESPACE

import rox
from rox import g

fixed_ns = {'xml': XML_NAMESPACE, 'xmlns': XMLNS_NAMESPACE,
	    'ext': FT_EXT_NAMESPACE,
	    'dome': DOME_NS}

common_ns = {'http://www.w3.org/1999/xhtml': 'xhtml',
	     'http://www.w3.org/1999/02/22-rdf-syntax-ns#': 'rdf',
	     'http://xmlns.4suite.org/ext': 'ft',
	     'http://www.w3.org/1999/XSL/Transform': 'xsl',
	     'http://www.w3.org/2001/XMLSchema': 'xsd',
	     'http://www.w3.org/1999/XMLSchema-instance': 'xsi',
	     'http://schemas.xmlsoap.org/soap/envelope/': 'env',
	     'http://www.w3.org/1999/xlink': 'xlink'}

class Namespaces(g.GenericTreeModel):
	def __init__(self):
		g.GenericTreeModel.__init__(self)
		self.uri = dict(fixed_ns)
		self.update_list()
	
	def update_list(self):
		self.list = self.uri.keys()
		self.list.sort()
		pre = self.prefix = {}
		for p, u in self.uri.iteritems():
			pre[u] = p
	
	def on_get_n_columns(self):
		return 2
	
	def on_get_iter(self, path):
		assert len(path) == 1
		return path[0]
	
	def on_get_value(self, iter, column):
		if column == 0:
			return self.list[iter]
		return self.uri[self.list[iter]]
	
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
		if prefix in self.uri and self.uri[prefix] == uri:
			return

		assert prefix
		if prefix in fixed_ns:
			raise Exception('That namespace prefix cannot be changed')
		if uri in self.prefix:
			raise Exception('That namespace already has a prefix (%s)' % self.prefix[uri])

		modifed = prefix in self.uri

		self.uri[prefix] = uri
		self.update_list()
		path = (self.list.index(prefix),)

		if modifed:
			self.emit('row-changed', path, self.get_iter(path))
		else:
			self.emit('row-inserted', path, self.get_iter(path))
	
	def __delitem__(self, iter):
		prefix = self[iter][0]
		if prefix in fixed_ns:
			raise Exception('This is a built-in namespace and cannot be deleted')
		path = (self.list.index(prefix),)
		del self.uri[prefix]
		self.update_list()
		self.emit('row-deleted', path)
	
	def ensure_ns(self, suggested_prefix, uri):
		"""Return the prefix for this URI. If none is set choose one (using suggested_prefix
		if possible)."""
		try:
			return self.prefix[uri]
		except KeyError:
			if not suggested_prefix:
				suggested_prefix = common_ns.get(uri, 'ns')
			if suggested_prefix in self.uri:
				x = 1
				while suggested_prefix + `x` in self.uri: x += 1
				suggested_prefix += `x`
			self[suggested_prefix] = uri
			#print "Added", suggested_prefix, uri
			return suggested_prefix
	
	def to_xml(self, doc):
		node = doc.createElementNS(DOME_NS, 'dome:namespaces')
		for prefix, uri in self.uri.iteritems():
			if prefix in fixed_ns: continue
			ns = doc.createElementNS(DOME_NS, 'dome:ns')
			ns.setAttributeNS(None, 'prefix', prefix)
			ns.setAttributeNS(None, 'uri', uri)
			node.appendChild(ns)
		return node

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
				dialog.add_new(model.namespaces)
			elif resp == 2:
				dialog.delete_selected(tree.get_selection())
			else:
				dialog.destroy()
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
	
	def add_new(self, ns):
		d = rox.Dialog()

		hbox = g.HBox(False, 2)
		d.vbox.pack_start(hbox, False, True)
		hbox.pack_start(g.Label('Prefix:'), False, True, 0)
		prefix = g.Entry()
		hbox.pack_start(prefix, True, True, 0)

		def check_prefix(entry):
			if not uri.get_text():
				pre = prefix.get_text()
				for u, p in common_ns.iteritems():
					if p == pre:
						uri.set_text(u)
						break
			uri.grab_focus()
					
		prefix.connect('activate', check_prefix)

		hbox = g.HBox(False, 2)
		d.vbox.pack_start(hbox, False, True)
		hbox.pack_start(g.Label('Namespace URI:'), False, True, 0)
		uri = g.Entry()
		hbox.pack_start(uri, True, True, 0)
		uri.set_activates_default(True)

		d.vbox.show_all()
		d.set_position(g.WIN_POS_MOUSE)

		prefix.grab_focus()
		
		d.add_button(g.STOCK_CANCEL, g.RESPONSE_CANCEL)
		d.add_button(g.STOCK_OK, g.RESPONSE_OK)
		
		d.set_default_response(g.RESPONSE_OK)

		while 1:
			if d.run() != g.RESPONSE_OK:
				d.destroy()
				return
			try:
				ns[prefix.get_text()] = uri.get_text()
				break
			except:
				rox.report_exception()
		d.destroy()
