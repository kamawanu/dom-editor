import sys
import traceback
from Ft.Xml.Domlette import Node, implementation
from Ft.Xml import XMLNS_NAMESPACE
from Ft.Xml.Lib.Nss import GetAllNs

from string import find, lower, join
from socket import gethostbyaddr, gethostname

def node_to_xml(node):
	"Takes an XML node and returns an XML documentElement suitable for saving."
	root = implementation.createDocument(None, 'root', None)
	new = node.cloneNode(deep = 1)
	new = root.importNode(new, deep = 1)
	root.replaceChild(new, root.documentElement)
	return root

def node_to_html(node):
	"Takes an XML node and returns an HTML documentElement suitable for saving."
	root = implementation.createHTMLDocument('HTML document')
	def html(doc, node, html):
		new = doc.importNode(node.cloneNode(deep = 0), deep = 0)
		if node.nodeType == Node.ELEMENT_NODE:
			for a in node.attributes:
				new.setAttribute(a.localName, a.value)
			for k in node.childNodes:
				new.appendChild(html(doc, k, html))
		return new
	new = html(root, node, html)
	root.replaceChild(new, root.documentElement)
	return root

def send_to_file(data, path):
	try:
		file = open(path, 'wb')
		try:
			file.write(data)
		finally:
			file.close()
	except:
		from rox import support

		support.report_exception()
		return 0

	return 1

def import_with_ns(doc, node):
	print "Import"
	nss = GetAllNs(node)
	print "nss", nss
	print "node, doc", node, doc
	
	node = doc.importNode(node, 1)
	print "node", node
	for ns in nss.keys():
		if ns == 'xml':
			continue
		print "Set namespace:", ns, "->", nss[ns]
		uri = nss[ns]
		if ns or uri:
			if ns is None:
				ns = 'xmlns'
			else:
				ns = 'xmlns:' + ns
			node.setAttributeNS(XMLNS_NAMESPACE, ns, uri)
	print "Dome"
	return node
