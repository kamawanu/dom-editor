import sys
import traceback
from xml.dom import ext, Node, implementation

from string import find, lower, join
from socket import gethostbyaddr, gethostname

from gtk import *

from rox.support import *

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
		report_exception()
		return 0

	return 1

