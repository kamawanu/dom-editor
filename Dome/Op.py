from xml.parsers.xmlproc.utils import escape_attval
from xml.dom.ext.reader import PyExpat
from StringIO import StringIO
import string

from support import *

def load_xml(op_xml):
	reader = PyExpat.Reader()
	doc = reader.fromStream(StringIO(op_xml))
	return load(doc.documentElement)

# Node is a DOM node: <node action="...">[<fail>][<node>]</node>.
# Returns the start Op.
def load(node):
	attr = node.getAttributeNS('', 'action')
	action = eval(str(attr))
	if action[0] == 'chroot':
		action[0] = 'enter'
	elif action[0] == 'unchroot':
		action[0] = 'leave'
	elif action[0] == 'playback':
		action[0] = 'map'

	op = Op(action)
		
	next = node.getElementsByTagNameNS('', 'node')
	fail = node.getElementsByTagNameNS('', 'node')

	if len(next) > 1:
		raise Exception('Invalid Op XML (too many next nodes)')
	if len(fail) > 1:
		raise Exception('Invalid Op XML (too many fail nodes)')

	if next:
		op.link_to(load(next.childNodes[0], 'next'))
	if fail:
		op.link_to(load(fail.childNodes[0], 'fail'))
	
	return op

class Op:
	"Each node in a chain is an Op. There is no graphical stuff in here."

	def __init__(self, action = "Start"):
		"Creates a new node (can be linked into another node later)"
		self.action = action
		self.next = None
		self.fail = None
		self.prev = None
		self.watchers = []
	
	def changed(self):
		print "Op(%s) changed." % self.action
		for w in self.watchers:
			w(self)
	
	def link_to(self, child, exit):
		# Create a link from this exit to this child Op
		if getattr(self, exit) != None:
			raise Exception('%s already has a %s child op!' % (self, exit))
		setattr(self, exit, child)
		self.changed()
	
	def unlink(self, child):
		"child becomes a Start node"
		if child.prev != self:
			raise Exception('forget_child: not my child!')
		child.prev = None

		if child == self.next:
			exit = 'next'
		else:
			exit = 'fail'
		setattr(self, exit, None)

		self.changed()

	def swap_nf(self):
		self.next, self.fail = (self.fail, self.next)
		self.changed()
	
	def del_node(self):
		"Remove this node, linking our next and previous nodes."
		"Error if we have fail and next nodes..., or if we have no prev node"
		if self.next and self.fail:
			raise Exception("Can't delete a node with both fail and next exits in use.")
		if not self.prev:
			raise Exception("Can't delete a Start node!")

		if self.next:
			next = self.next
		else:
			next = self.fail

		if next:
			next.prev = None

		prev = self.prev
		if prev.next == self:
			exit = 'next'
		else:
			exit = 'fail'
		prev.link_to(next, exit)

		self.action = None
		self.prev = None
		self.next = None
		self.fail = None
	
	def del_chain(self):
		xml = self.to_xml()
		self.prev.unlink(self)
		return xml
	
	def to_xml(self):
		next = self.next
		fail = self.fail
		act = escape_attval(`self.action`)
		ret = '<node action="%s"' % act
		if next == None and fail == None:
			return ret + '/>\n'
		ret += '>\n'

		if fail:
			ret += '<fail>\n' + fail.add() + '</fail>'

		if next:
			return ret + next.add() + '</node>'
		return ret + '</node>'
	
	def __str__(self):
		return "{" + `self.action` + "}"

