from xml.dom import Node

def literal_match(node):
	return "[ext:match('%s')]" % node.nodeValue

# Return a string that will match this node in an XPath.
# ns is updated with any new namespace required.
def match_name(node, ns):
	if node.nodeType == Node.TEXT_NODE:
		return 'text()'
	elif node.nodeType == Node.COMMENT_NODE:
		return 'comment()'
	elif node.nodeType == Node.ELEMENT_NODE:
		if node.namespaceURI:
			for x in ns.keys():
				if ns[x] == node.namespaceURI:
					return '%s:%s' % (x, node.localName)
			n = 1
			while 1:
				key = '_ns_%d' % n
				if not ns.has_key(key):
					break
				n += 1
			ns[key] = node.namespaceURI
			return '%s:%s' % (key, node.localName)
		return node.nodeName
	else:
		return node.nodeName

def jump_to_sibling(src, dst, ns):
	"Return an XPath which, given a context 'src' will move to sibling 'dst'."
	"Namespace 'ns' may be updated if new names are required"

	if dst.nodeType == Node.ATTRIBUTE_NODE:
		return 'attribute::%s/' % dst.nodeName

	# Search forwards for 'dst', counting how many matching nodes we pass.
	count = 0
	check = src
	while check != dst:
		check = check.nextSibling
		if not check:
			break
		if check.nodeName == dst.nodeName:
			count += 1
	if check:
		return 'following-sibling::%s[%d]/' % (match_name(dst, ns), count)

	# Not found - search backwards for 'dst', counting how many matching nodes we pass.
	count = 0
	check = src
	while check != dst:
		check = check.previousSibling
		if not check:
			return			# Error!
		if check.nodeName == dst.nodeName:
			count += 1
	return 'preceding-sibling::%s[%d]/' % (match_name(dst, ns), count)

def make_relative_path(src_node, dst_node, lit, ns):
	"Return an XPath string which will move us from src to dst."
	"If 'lit' then the text of the (data) node must match too."
	"Namespace 'ns' is updated with any required namespaces."

	if src_node == dst_node:
		return '.'

	def path_to(node):
		"Returns a path to the node in the form [root, ... , node]"
		ps = [node]
		while node.parentNode:
			node = node.parentNode
			ps.insert(0, node)
		return ps

	src_parents = path_to(src_node)
	dst_parents = path_to(dst_node)

	# Trim off all the common path elements...
	# Note that this may leave either path empty, if one node is an ancestor of the other.
	while src_parents and dst_parents and src_parents[0] == dst_parents[0]:
		del src_parents[0]
		del dst_parents[0]

	# Now, the initial context node is 'src_node'.
	# Build the path from here...
	path = ''

	# We need to go up one level for each element left in src_parents, less one
	# (so we end up as a child of the lowest common parent, on the src side).
	# If src is an ancestor of dst then this does nothing.
	# If dst is an ancestor of src then go up an extra level, because we don't jump
	# across in the next step.
	for p in range(0, len(src_parents) - 1):
		path += '../'
	if not dst_parents:
		path += '../'

	# We then jump across to the correct sibling and head back down the tree...
	# If src is an ancestor of dst or the other way round we do nothing.
	if src_parents and dst_parents:
		path += jump_to_sibling(src_parents[0], dst_parents[0], ns)
		del dst_parents[0]

	# dst_parents is now a list of nodes to visit to get to dst.
	for node in dst_parents:
		prev = 1
		
		p = node
		while p.previousSibling:
			p = p.previousSibling
			if p.nodeName == node.nodeName:
				prev += 1
		
		path += 'child::%s[%d]/' % (match_name(node, ns), prev)

	path = path[:-1]
	if lit:
		path += literal_match(dst_node)
	#print "%s [%s]" % (path, ns)
	return path
