# An model contains:
# - A DOM document
# - The undo history
# All changes to the DOM must go through here.
# Notification to views of changes is done.

from xml.dom import implementation, XMLNS_NAMESPACE
from xml.dom import ext
from xml.dom import Node
from xml.dom.Document import Document
import string
import Html
import Change
from Beep import Beep

from support import html_to_xml

class Model:
	def __init__(self, uri):
		self.doc = implementation.createDocument('', 'root', None)
		self.views = []		# Notified when something changes
		self.locks = {}		# Node -> number of locks
		if uri:
			self.uri = uri
		else:
			self.uri = 'Document'
	
	def lock(self, node):
		"""Prevent removal of this node (or any ancestor)."""
		print "Locking", node.nodeName
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
		m = Model(self.get_base_uri(node))
		copy = m.doc.importNode(node, deep = 1)
		root = m.get_root()
		m.replace_node(root, copy)
		return m
		
	def mark(self):
		"Increment the user_op counter. Undo will undo every operation between"
		"two marks."
		Change.user_op += 1
	
	def get_root(self):
		"Return the true root node (not a view root)"
		return self.doc.documentElement
	
	def add_view(self, view):
		"'view' provides:"
		"'update_all(subtree) - called when a major change occurs."
		print "New view:", view
		self.views.append(view)
	
	def remove_view(self, view):
		print "Removing view", view
		self.views.remove(view)
		print "Now:", self.views

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
		Change.set_name(node, namespace, name)
		self.update_all(node)
	
	def set_data(self, node, data):
		Change.set_data(node, data)
		self.update_all(node)
	
	def replace_node(self, old, new):
		Change.replace_node(old, new)
		self.update_replace(old, new)
	
	def delete_nodes(self, nodes):
		print "Deleting", nodes
		for n in nodes:
			if self.get_locks(n):
				raise Exception('Attempt to delete locked node %s' % n)
		for n in nodes:
			p = n.parentNode
			Change.delete(n)
			self.update_all(p)

	def undo(self, node):
		uop = None
		while 1:
			result = Change.do_undo(node, uop)
			if result is None:
				return
			alt_node, uop = result
			print "Undid with uop =", uop
			self.update_all(alt_node)

	def redo(self, node):
		uop = None
		while 1:
			result = Change.do_redo(node, uop)
			if result is None:
				return
			alt_node, uop = result
			print "Redid with uop =", uop
			self.update_all(alt_node)
	
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
				Change.insert_before(node, n, parent)
		else:
			Change.insert_before(node, new, parent)
		self.update_all(parent)
	
	def set_attrib(self, node, namespaceURI, localName, value):
		"Set an attribute's value. If value is None, remove the attribute."
		Change.set_attrib(node, namespaceURI, localName, value)
		self.update_all(node)
	
	def prefix_to_namespace(self, node, prefix):
		"Use the xmlns attributes to workout the namespace."
		nss = ext.GetAllNs(node)
		if nss.has_key(prefix):
			return nss[prefix]
		if prefix:
			if prefix == 'xmlns':
				return XMLNS_NAMESPACE
			raise Exception("No such namespace prefix '%s'" % prefix)
		else:
			return ''

	def get_base_uri(self, node):
		"""Go up through the parents looking for a uri attribute.
		If there isn't one, use the document's URI."""
		while node:
			if isinstance(node, Document):
				return self.uri
			if node.hasAttributeNS('', 'uri'):
				return node.getAttributeNS('', 'uri')
			node = node.parentNode
		return None

