from __future__ import nested_scopes

# An model contains:
# - A DOM document
# - The undo history
# - The root program
# All changes to the DOM must go through here.
# Notification to views of changes is done.

from Ft.Xml.cDomlette import implementation, nonvalParse
from Ft.Xml import XMLNS_NAMESPACE
from xml.dom import ext
from xml.dom import Node
from xml.dom.Document import Document
import string
import Html
import support
from Beep import Beep

class Model:
	def __init__(self, path, root_program = None):
		"If root_program is given, then no data is loaded (used for lock_and_copy)."
		self.uri = 'Document'

		# Pop an (op_number, function) off one of these and call the function to
		# move forwards or backwards in the undo history.
		self.undo_stack = []
		self.redo_stack = []
		self.doing_undo = 0

		# Each series of suboperations in an undo stack which are part of a single
		# user op will have the same number...
		self.user_op = 1
		
		doc = None
		if path:
			if path != '-':
				self.uri = path
			if not root_program:
				#from xml.dom.ext.reader import PyExpat
				from Ft.Xml.InputSource import InputSourceFactory
				isrc = InputSourceFactory()
				doc = nonvalParse(isrc.fromUri(path))
		if not doc:
			doc = implementation.createDocument(None, 'root', None)
		root = doc.documentElement

		self.root_program = None
		data_to_load = None

		from Program import Program, load_dome_program
		import constants
		if root.namespaceURI == constants.DOME_NS and root.localName == 'dome':
			for x in root.childNodes:
				if x.namespaceURI == constants.DOME_NS:
					if x.localName == 'dome-program':
						self.root_program = load_dome_program(x)
					elif x.localName == 'dome-data':
						for y in x.childNodes:
							if y.nodeType == Node.ELEMENT_NODE:
								data_to_load = y
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
				node = support.import_with_ns(self.doc, data_to_load)
				self.doc.replaceChild(node, self.doc.documentElement)
				self.strip_space()
		
		self.views = []		# Notified when something changes
		self.locks = {}		# Node -> number of locks

	def lock(self, node):
		"""Prevent removal of this node (or any ancestor)."""
		#print "Locking", node.nodeName
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
		self.lock(node)
		m = Model(self.get_base_uri(node), root_program = self.root_program)
		copy = support.import_with_ns(m.doc, node)
		root = m.get_root()
		m.replace_node(root, copy)
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
		if node.nodeType == Node.TEXT_NODE:
			node.data = string.strip(node.data)
			if node.data == '':
				node.parentNode.removeChild(node)
		else:
			for k in node.childNodes[:]:
				self.strip_space(k)

	# Changes
	
	def set_name(self, node, namespace, name):
		if self.get_locks(node):
			raise Exception('Attempt to set name on locked node %s' % node)

		old_name = node.nodeName
		old_ns = node.namespaceURI

		kids = node.childNodes[:]
		attrs = node.attributes.values()
		parent = node.parentNode
		[ node.removeChild(k) for k in kids ]
		new = node.ownerDocument.createElementNS(namespace, name)
		parent.replaceChild(new, node)
		[ new.appendChild(k) for k in kids ]
		[ new.setAttributeNS(a.namespaceURI, a.name, a.value) for a in attrs ]

		self.add_undo(lambda: self.set_name(new, old_ns, old_name))
	
		self.update_replace(node, new)
		return new

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
		"of parent's children."
		if not parent:
			parent = node.parentNode
		if new.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
			for n in new.childNodes[:]:
				self.insert_before_interal(node, n, parent)
		else:
			self.insert_before_interal(node, new, parent)
		self.update_all(parent)
	
	def split_qname(self, node, name):
		if name == 'xmlns':
			namespaceURI = XMLNS_NAMESPACE
			localName = name
		elif ':' in name:
			prefix, localName = string.split(name, ':')
			namespaceURI = self.prefix_to_namespace(node, prefix)
		else:
			namespaceURI = None
			localName = name
		return namespaceURI, localName
	
	def set_attrib(self, node, name, value, with_update = 1):
		"""Set an attribute's value. If value is None, remove the attribute.
		Returns the new attribute node, or None if removing."""
		namespaceURI, localName = self.split_qname(node, name)

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
		"Use the xmlns attributes to workout the namespace."
		nss = ext.GetAllNs(node)
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

