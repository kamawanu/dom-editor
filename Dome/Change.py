# All changes go through here so we can undo...

def insert(node, new, index = 0):
	node.parentNode.insertBefore(new, node.childNodes[0])

def insert_before(node, new):
	node.parentNode.insertBefore(new, node)
	
def insert_after(node, new):
	node.parentNode.insertBefore(new, node.nextSibling)
	
def delete(node):
	node.parentNode.removeChild(node)
