# All changes go through here so we can undo...

from Beep import Beep
from xml.dom import Node

# Which undo list operations will affect.
# Normal ops add to the undo list.
# Undo ops add to the redo list.
# Redo ops add to the undo list, but don't clear the redo list.
undo_state = '__dom_undo'
undo_clear = 1

# This value is stored with each undo record.
# The caller may use this to indicate whether several operations
# should be considered as one.
user_op = 1

# These actually modifiy the DOM
def set_name(node, namespaceURI, qname):
	# XXX: Hack!
	tmp = node.ownerDocument.createElementNS(namespaceURI, qname)
	add_undo(node, lambda node = node, ns = node.namespaceURI, name = node.nodeName:
			set_name(node, ns, name))
	node.__dict__['__nodeName'] = tmp.__dict__['__nodeName']
	node.__dict__['__namespaceURI'] = tmp.__dict__['__namespaceURI']
        node.__dict__['__prefix'] = tmp.__dict__['__prefix']
        node.__dict__['__localName'] = tmp.__dict__['__localName']

def insert_before(node, new, parent):
	"Insert 'new' before 'node'. If 'node' is None then insert at the end"
	"of parent's children."
	if new.nodeType == Node.DOCUMENT_FRAGMENT_NODE:
		raise Exception("insert_before() can't take a fragment!")
	parent.insertBefore(new, node)
	add_undo(parent, lambda new = new: delete(new))
	
def delete(node):
	next = node.nextSibling
	parent = node.parentNode
	parent.removeChild(node)
	add_undo(parent,
		lambda parent = parent, next = next, node = node:
				insert_before(next, node, parent = parent))

def replace_node(old, new):
	old.parentNode.replaceChild(new, old)
	add_undo(new.parentNode,
		lambda old = old, new = new:
			replace_node(new, old))

def set_data(node, new):
	old = node.data
	node.data = new
	add_undo(node,
		lambda node = node, old = old:
			set_data(node, old))

def set_attrib(node, namespaceURI, localName, value = None):
	#print "set_attrib", `namespaceURI`, `localName`, `value`
	if node.hasAttributeNS(namespaceURI, localName):
		old = node.getAttributeNS(namespaceURI, localName)
	else:
		old = None
	if value != None:
		if localName == None:
			localName = 'xmlns'
		node.setAttributeNS(namespaceURI, localName, value)
	else:
		node.removeAttributeNS(namespaceURI, localName)

	add_undo(node, lambda node = node, namespaceURI = namespaceURI, localName = localName, old = old: \
				set_attrib(node, namespaceURI, localName, old))

# Support

op = 0

def newest_change(node, history):
	"Return the most recent (node,time) change to the 'history' list."

	try:
		best_node, best_time = node, getattr(node, history)[-1][0]
	except:
		best_node, best_time = None, 0
	
	for k in node.childNodes:
		n, t = newest_change(k, history)
		if n and (best_node == None or t > best_time):
			best_node, best_time = n, t
	return best_node, best_time

def can_undo(node):
	n, t = newest_change(node, '__dom_undo')
	return n != None

def can_redo(node):
	n, t = newest_change(node, '__dom_redo')
	return n != None

# Undo and redo stuff
# XXX: Undo/redo need to check locking
def add_undo(node, fn):
	"Attempting to undo changes to 'node' will call this fn."
	#return	#Disabled
	global op
	op += 1
	
	if not hasattr(node, undo_state):
		setattr(node, undo_state, [])
	getattr(node, undo_state).append((op, fn, user_op))
	if undo_clear and hasattr(node, '__dom_redo'):
		del node.__dom_redo

def do_undo(node, user_op = None):
	"Undo changes to this node (including descendants)."
	"Returns the node containing the undone node, and the user_op."
	"If 'user_op' is given, only undo if it matches, else return None."
	node, time = newest_change(node, '__dom_undo')
	if not node:
		return
	op, fn, uop = node.__dom_undo[-1]
	if user_op and user_op != uop:
		return
	parent = node.parentNode
	
	del node.__dom_undo[-1]

	global undo_state, undo_clear
	undo_state = '__dom_redo'
	undo_clear = 0
	fn()
	undo_clear = 1
	undo_state = '__dom_undo'

	return (parent, uop)

def do_redo(node, user_op = None):
	"Redo undos on this node (including descendants)."
	"Returns the node containing the redone node, and the user_op."
	"If 'user_op' is given, only redo if it matches, else return None."
	node, time = newest_change(node, '__dom_redo')
	if not node:
		return
	op, fn, uop = node.__dom_redo[-1]
	if user_op and user_op != uop:
		return
	parent = node.parentNode
	
	del node.__dom_redo[-1]

	global undo_state, undo_clear
	undo_clear = 0
	fn()
	undo_clear = 1

	return (parent, uop)
