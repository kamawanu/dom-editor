from xmllib import *
import string

from support import *
from Node import *

def load_xml(file):
	try:
		l = Loader(file)
		f = open(file, 'rb')
		l.feed(f.read())
		l.close()
		return l.root
	except:
		report_exception()

class Loader(XMLParser):
	def __init__(self, path):
		XMLParser.__init__(self)
		f = open(path, 'rb')
		self.root = None
		self.current = None
		self.buffer = ""
	
	def unknown_starttag(self, tag, attribs):
		self.do_buffered()

		n = Node(tag, attribs)
		if self.current:
			self.current.add(n, undo = 0)
		self.current = n

		if not self.root:
			self.root = n
	
	def unknown_endtag(self, tag):
		self.do_buffered()
		self.current = self.current.parent
	
	def do_buffered(self):
		b = string.strip(self.buffer)
		if b and self.current:
			self.current.add(DataNode(b), undo = 0)
			self.buffer = ""
	
	def handle_data(self, data):
		if not self.current:
			return
		self.buffer = self.buffer + data
