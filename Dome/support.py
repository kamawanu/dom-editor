import sys
import traceback
from xml.dom import ext, Node, implementation

from string import find, lower, join
from socket import gethostbyaddr, gethostname

from gtk import *

from rox.MultipleChoice import MultipleChoice
from rox.support import *

def node_to_xml(node):
	"Takes an XML node and returns an XML documentElement suitable for saving."
	root = implementation.createDocument('', 'root', None)
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

def set_default_namespace(node):
	"Attributes get a namespace of ''."
	if node.nodeType == Node.ELEMENT_NODE:
		old = []
		for a in node.attributes:
			old.append((a.name, a.value))
		for (name, value) in old:
			node.removeAttribute(name)
			node.setAttributeNS('', name, value)
	for k in node.childNodes:
		set_default_namespace(k)

def html_to_xml(doc, html):
	"Takes an HTML DOM (modified) and creates a corresponding XML DOM."
	"Attributes are given the namespace ''."
	ext.StripHtml(html)
	old_root = html.documentElement
	node = doc.importNode(old_root, deep = 1)
	set_default_namespace(node)
	return node

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

