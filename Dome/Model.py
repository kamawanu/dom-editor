from __future__ import nested_scopes

# An model contains:
# - A DOM document
# - The undo history
# - The root program
# All changes to the DOM must go through here.
# Notification to views of changes is done.

from Ft.Xml.cDomlette import implementation, nonvalParse
from Ft.Xml.Domlette import GetAllNs
from Ft.Xml import XMLNS_NAMESPACE

from xml.dom import Node
import support
from Beep import Beep
import constants

class Model:
	def __init__(self, path, root_program = None, dome_data = None, do_load = 1):
		"If root_program is given, then no data is loaded (used for lock_and_copy)."
		self.uri = 'Prog.dome'
		import Namespaces
		self.namespaces = Namespaces.Namespaces() 

		if dome_data:
			from Ft.Xml.InputSource import InputSourceFactory
			isrc = InputSourceFactory()
			dome_data = nonvalParse(isrc.fromUri(dome_data))

		self.clear_undo()

		doc = None
		if path:
			if path != '-':
				self.uri = path
			if do_load and (path.endswith('.html') or path.endswith('.htm')):
				doc = self.load_html(path)
			if not doc and not root_program:
				from Ft.Xml.InputSource import InputSourceFactory
				isrc = InputSourceFactory()
				try:
					doc = nonvalParse(isrc.fromUri(path))
				except:
					import rox
					rox.report_exception()
		if not doc:
			doc = implementation.createDocument(None, 'root', None)
		root = doc.documentElement

		self.root_program = None
		data_to_load = None

		from Program import Program, load_dome_program
		print root.namespaceURI, root.localName
		if root.namespaceURI == constants.DOME_NS and root.localName == 'dome':
			for x in root.childNodes:
				if x.namespaceURI == constants.DOME_NS:
					if x.localName == 'namespaces':
						self.load_ns(x)
					elif x.localName == 'dome-program':
						self.root_program = load_dome_program(x,
										self.namespaces)
					elif x.localName == 'dome-data':
						for y in x.childNodes:
							if y.nodeType == Node.ELEMENT_NODE:
								data_to_load = y
			if dome_data:
				data_to_load = dome_data.documentElement
		elif (root.namespaceURI == constants.XSLT_NS and 
		      root.localName in ['stylesheet', 'transform']) or \
		      root.hasAttributeNS(constants.XSLT_NS, 'version'):
			import xslt
			self.root_program = xslt.import_sheet(doc)
			self.doc = implementation.createDocument(None, 'xslt', None)
			data_to_load = None
			src = self.doc.createElementNS(None, 'Source')
			if dome_data:
				src.appendChild(self.import_with_ns(dome_data.documentElement))
			self.doc.documentElement.appendChild(src)
			self.doc.documentElement.appendChild(self.doc.createElementNS(None, 'Result'))
			self.strip_space()
			data_to_load = None
			dome_data = None
		else:
			data_to_load = root

		if root_program:
			self.root_program = root_program
		else:
			if not self.root_program:
				self.root_program = Program('Root')

		if data_to_load:
			self.doc = implementation.createDocument(None, 'root', None)
			if not root_program:
				node = self.import_with_ns(data_to_load)
				self.doc.replaceChild(node, self.doc.documentElement)
				self.strip_space()
		
		self.views = []		# Notified when something changes
		self.locks = {}		# Node -> number of locks

		self.hidden = {}	# Node -> Message
		self.hidden_code = {}	# XPath to generate Message, if any
	
	def load_ns(self, node):
		assert node.localName == 'namespaces'
		assert node.namespaceURI == constants.DOME_NS
		for x in node.childNodes:
			if x.nodeType != Node.ELEMENT_NODE: continue
			if x.localName != 'ns': continue
			if x.namespaceURI != constants.DOME_NS: continue

			self.namespaces.ensure_ns(x.getAttributeNS(None, 'prefix'),
						  x.getAttributeNS(None, 'uri'))
	
	def import_with_ns(self, node):
		"""Return a copy of node for this model. All namespaces used in the subtree
		will have been added to the global namespaces list. Prefixes will have been changed
		as required to avoid conflicts."""
		doc = self.doc
		def ns_clone(node, clone):
			if node.nodeType != Node.ELEMENT_NODE:
				return doc.importNode(node, 1)
			if node.namespaceURI:
				prefix = self.namespaces.ensure_ns(node.prefix, node.namespaceURI)
				new = doc.createElementNS(node.namespaceURI,
							  prefix + ':' + node.localName)
			else:
				new = doc.createElementNS(None, node.localName)
			for a in node.attributes.values():
				if a.namespaceURI == XMLNS_NAMESPACE: continue
				new.setAttributeNS(a.namespaceURI, a.name, a.value)
			for k in node.childNodes:
				new.appendChild(clone(k, clone))
			return new
		new = ns_clone(node, ns_clone)
		return new
	
	def clear_undo(self):
		# Pop an (op_number, function) off one of these and call the function to
		# move forwards or backwards in the undo history.
		self.undo_stack = []
		self.redo_stack = []
		self.doing_undo = 0

		# Each series of suboperations in an undo stack which are part of a single
		# user op will have the same number...
		self.user_op = 1

		#import gc
		#print "GC freed:", gc.collect()
		#print "Garbage", gc.garbage

	def lock(self, node):
		"""Prevent removal of this node (or any ancestor)."""
		#print "Locking", node.nodeName
		assert node.nodeType
		self.locks[node] = self.get_locks(node) + 1
		if node.parentNode:
			self.lock(node.parentNode)
	
	def unlock(self, node):
		"""Reverse the effect of lock(). Must call unlock the same number
		of times as lock to fully unlock the node."""
		l = self.get_locks(node)
		if l > 1:
			self.locks[node] = l - 1
		elif l == 1:
			del self.locks[node]	# Or get a memory leak...
			if node == self.doc.documentElement:
				if node.parentNode:
					self.unlock(node.parentNode)
				return
		else:
			raise Exception('unlock(%s): Node not locked!' % node)
		if node.parentNode:
			self.unlock(node.parentNode)
	
	def get_locks(self, node):
		try:
			return self.locks[node]
		except KeyError:
			return 0
	
	def lock_and_copy(self, node):
		"""Locks 'node' in the current model and returns a new model
		with a copy of the subtree."""
		if self.get_locks(node):
			raise Exception("Can't enter locked node!")
		m = Model(self.get_base_uri(node), root_program = self.root_program, do_load = 0)
		copy = m.import_with_ns(node)
		root = m.get_root()
		m.replace_node(root, copy)
		self.lock(node)
		return m
		
	def mark(self):
		"Increment the user_op counter. Undo will undo every operation between"
		"two marks."
		self.user_op += 1
	
	def get_root(self):
		"Return the true root node (not a view root)"
		return self.doc.documentElement
	
	def add_view(self, view):
		"'view' provides:"
		"'update_all(subtree) - called when a major change occurs."
		#print "New view:", view
		self.views.append(view)
	
	def remove_view(self, view):
		#print "Removing view", view
		self.views.remove(view)
		#print "Now:", self.views
		# XXX: clears undo on enter!
		#if not self.views:
		#	self.clear_undo()
	
	def update_all(self, node):
		"Called when 'node' has been updated."
		"'node' is still in the document, so deleting or replacing"
		"a node calls this on the parent."
		for v in self.views:
			v.update_all(node)

	def update_replace(self, old, new):
		"Called when 'old' is replaced by 'new'."
		for v in self.views:
			v.update_replace(old, new)

	def strip_space(self, node = None):
		if not node:
			node = self.doc.documentElement
		def ss(node):
			if node.nodeType == Node.TEXT_NODE:
				#node.data = node.data.strip()
				#if node.data == '':
				#	node.parentNode.removeChild(node)
				if not node.data.strip():
					node.parentNode.removeChild(node)
			else:
				for k in node.childNodes[:]:
					ss(k)
		ss(node)

	# Changes

	def normalise(self, node):
		old = node.cloneNode(1)
		node.normalize()
		self.add_undo(lambda: self.replace_node(node, old))
		self.update_all(node)
	
	def convert_to_element(self, node):
		assert node.nodeType in (Node.COMMENT_NODE, Node.PROCESSING_INSTRUCTION_NODE,
					 Node.TEXT_NODE)
		new = self.doc.createElementNS(None, node.data.strip())
		self.replace_node(node, new)
		return new
	
	def convert_to_text(self, node):
		assert node.nodeType in (Node.COMMENT_NODE, Node.PROCESSING_INSTRUCTION_NODE,
					 Node.TEXT_NODE, Node.ELEMENT_NODE)
		if node.nodeType == Node.ELEMENT_NODE:
			new = self.doc.createTextNode(node.localName)
		else:
			new = self.doc.createTextNode(node.data)
		self.replace_node(node, new)
		return new
	
	def convert_to_comment(self, node):
		assert node.nodeType in (Node.COMMENT_NODE, Node.PROCESSING_INSTRUCTION_NODE,
					 Node.TEXT_NODE)
		new = self.doc.createComment(node.data)
		self.replace_node(node, new)
		return new
	
	def remove_ns(self, node):
		print "remove_ns: Shouldn't need this now!"
		return

		nss = GetAllNs(node.parentNode)
		dns = nss.get(None, None)
		create = node.ownerDocument.createElementNS
		# clone is an argument to fix a wierd gc bug in python2.2
		def ns_clone(node, clone):
			if node.nodeType != Node.ELEMENT_NODE:
				return node.cloneNode(1)
			new = create(dns, node.nodeName)
			for a in node.attributes.values():
				if a.localName == 'xmlns' and a.prefix is None:
					print "Removing xmlns attrib on", node
					continue
				new.setAttributeNS(a.namespaceURI, a.name, a.value)
			for k in node.childNodes:
				new.appendChild(clone(k, clone))
			return new
		new = ns_clone(node, ns_clone)
		self.replace_node(node, new)
		return new
	
	def set_name(self, node, namespace, name):
		if self.get_locks(node):
			raise Exception('Attempt to set name on locked node %s' % node)

		new = node.ownerDocument.createElementNS(namespace, name)
		self.replace_shallow(node, new)
		return new
	
	def replace_shallow(self, old, new):
		"""Replace old with new, keeping the old children."""
		assert not new.childNodes
		assert not new.parentNode

		old_name = old.nodeName
		old_ns = old.namespaceURI

		kids = old.childNodes[:]
		attrs = old.attributes.values()
		parent = old.parentNode
		[ old.removeChild(k) for k in kids ]
		parent.replaceChild(new, old)
		[ new.appendChild(k) for k in kids ]
		[ new.setAttributeNS(a.namespaceURI, a.name, a.value) for a in attrs ]

		self.add_undo(lambda: self.replace_shallow(new, old))
	
		self.update_replace(old, new)

	import __main__
	if __main__.no_gui_mode:
		def add_undo(self, fn):
			pass
	else:
		def add_undo(self, fn):
			self.undo_stack.append((self.user_op, fn))
			if not self.doing_undo:
				self.redo_stack = []

	def set_data(self, node, data):
		old_data = node.data
		node.data = data
		self.add_undo(lambda: self.set_data(node, old_data))
		self.update_all(node)
	
	def replace_node(self, old, new):
		if self.get_locks(old):
			raise Exception('Attempt to replace locked node %s' % old)
		old.parentNode.replaceChild(new, old)
		self.add_undo(lambda: self.replace_node(new, old))
		
		self.update_replace(old, new)

	def delete_shallow(self, node):
		"""Replace node with its contents"""
		kids = node.childNodes[:]
		next = node.nextSibling
		parent = node.parentNode
		for n in kids + [node]:
			if self.get_locks(n):
				raise Exception('Attempt to move/delete locked node %s' % n)
		for k in kids:
			self.delete_internal(k)
		self.delete_internal(node)
		for k in kids:
			self.insert_before_interal(next, k, parent)
		self.update_all(parent)
	
	def delete_nodes(self, nodes):
		#print "Deleting", nodes
		for n in nodes:
			if self.get_locks(n):
				raise Exception('Attempt to delete locked node %s' % n)
		for n in nodes:
			p = n.parentNode
			self.delete_internal(n)
			self.update_all(p)
	
	def delete_internal(self, node):
		"Doesn't update display."
		next = node.nextSibling
		parent = node.parentNode
		parent.removeChild(node)
		self.add_undo(lambda: self.insert_before(next, node, parent = parent))
	
	def insert_before_interal(self, node, new, parent):
		"Insert 'new' before 'node'. If 'node' is None then insert at the end"
		"of parent's children."
		assert new.nodeType != Node.DOCUMENT_FRAGMENT_NODE
		#assert parent.nodeType == Node.ELEMENT_NODE
		parent.insertBefore(new, node)
		self.add_undo(lambda: self.delete_nodes([new]))

	def undo(self):
		if not self.undo_stack:
			raise Exception('Nothing to undo')

		assert not self.doing_undo

		uop = self.undo_stack[-1][0]

		# Swap stacks so that the undo actions will populate the redo stack...
		(self.undo_stack, self.redo_stack) = (self.redo_stack, self.undo_stack)
		self.doing_undo = 1
		try:
			while self.redo_stack and self.redo_stack[-1][0] == uop:
				self.redo_stack[-1][1]()
				self.redo_stack.pop()
		finally:
			(self.undo_stack, self.redo_stack) = (self.redo_stack, self.undo_stack)
			self.doing_undo = 0

	def redo(self):
		if not self.redo_stack:
			raise Exception('Nothing to redo')

		uop = self.redo_stack[-1][0]
		self.doing_undo = 1
		try:
			while self.redo_stack and self.redo_stack[-1][0] == uop:
				self.redo_stack[-1][1]()
				self.redo_stack.pop()
		finally:
			self.doing_undo = 0
	
	def insert(self, node, new, index = 0):
		if len(node.childNodes) > index:
			self.insert_before(node.childNodes[index], new)
		else:
			self.insert_before(None, new, parent = node)

	def insert_after(self, node, new):
		self.insert_before(node.nextSibling, new, parent = node.parentNode)

	def insert_before(self, node, new, parent = None):
		"Insert 'new' before 'node'. If 'node' is None then insert at the end"
		"of parent's children. New may be a node, a list or a fragment."
		if not parent:
			parent = node.parentNode
		if type(new) != list:
			if new.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
				new = new.childNodes
			else:
				new = [new]
		for n in new: self.insert_before_interal(node, n, parent)
		self.update_all(parent)
	
	def split_qname(self, node, name):
		if name == 'xmlns':
			namespaceURI = XMLNS_NAMESPACE
			localName = name
		elif ':' in name:
			prefix, localName = name.split(':')
			namespaceURI = self.prefix_to_namespace(node, prefix)
		else:
			namespaceURI = None
			localName = name
		return namespaceURI, localName
	
	def set_attrib(self, node, name, value, with_update = 1):
		"""Set an attribute's value. If value is None, remove the attribute.
		Returns the new attribute node, or None if removing."""
		namespaceURI, localName = self.split_qname(node, name)

		if namespaceURI == XMLNS_NAMESPACE:
			raise Exception("Attempt to set namespace attribute '%s'.\n\n"
					"Use View->Show Namespaces to edit namespaces." % name)

		if node.hasAttributeNS(namespaceURI, localName):
			old = node.getAttributeNS(namespaceURI, localName)
		else:
			old = None
		#print "Set (%s,%s) = %s" % (namespaceURI, name, value)
		if value != None:
			node.setAttributeNS(namespaceURI, name, value)
		else:
			node.removeAttributeNS(namespaceURI, localName)

		self.add_undo(lambda: self.set_attrib(node, name, old))
		
		if with_update:
			self.update_all(node)
		if value != None:
			if localName == 'xmlns':
				localName = None
			return node.attributes[(namespaceURI, localName)]
	
	def prefix_to_namespace(self, node, prefix):
		"Using attributes for namespaces was too confusing. Keep a global list instead."
		if prefix is None: return None
		try:
			return self.namespaces.uri[prefix]
		except KeyError:
			raise Exception("Namespace '%s' is not defined. Choose "
				"View->Show namespaces from the popup menu to set it." % prefix)
		
		"Use the xmlns attributes to workout the namespace."
		nss = GetAllNs(node)
		if nss.has_key(prefix):
			return nss[prefix] or None
		if prefix:
			if prefix == 'xmlns':
				return XMLNS_NAMESPACE
			raise Exception("No such namespace prefix '%s'" % prefix)
		else:
			return None

	def get_base_uri(self, node):
		"""Go up through the parents looking for a uri attribute.
		If there isn't one, use the document's URI."""
		while node:
			if node.nodeType == Node.DOCUMENT_NODE:
				return self.uri
			if node.hasAttributeNS(None, 'uri'):
				return node.getAttributeNS(None, 'uri')
			node = node.parentNode
		return None
	
	def load_html(self, path):
		"""Load this HTML file and return the new document."""
		data = file(path).read()
		data = support.to_html_doc(data)
		doc = support.parse_data(data, path)
		self.strip_space(doc)
		return doc
