from gtk import *
from GDK import *
from xml.dom.Node import Node

from support import report_exception

from Display import Display
from Beep import Beep
from Menu import Menu
from GetArg import GetArg
from Path import make_relative_path
from Editor import edit_node
import Exec

class GUIView(Display):
	def __init__(self, window, view):
		Display.__init__(self, window, view)
		window.connect('key-press-event', self.key_press)

	def key_press(self, widget, kev):
		try:
			stop = self.handle_key(kev)
		except:
			report_exception()
			stop = 1
		if stop:
			widget.emit_stop_by_name('key-press-event')
		return stop

	def handle_key(self, kev):
		key = kev.keyval

		if key == F3 or key == Return:
			return 0

		try:
			action = self.key_to_action[key]
		except KeyError:
			return 0

		if callable(action):
			# Need to popup a dialog box, etc rather then perform an action
			action(self)
			return 1

		self.view.may_record(action)
		return 1
	
	def node_clicked(self, node, bev):
		if node:
			if len(self.view.current_nodes) == 0:
				src = self.view.root
			else:
				src = self.view.current_nodes[-1]
			lit = bev.state & SHIFT_MASK
			add = bev.state & CONTROL_MASK
			ns = {}
			path = make_relative_path(src, node, lit, ns)
			self.view.may_record(["do_search", path, ns, add])

	def attrib_clicked(self, element, attrib, event):
		if len(self.view.current_nodes) == 0:
			src = self.view.root
		else:
			src = self.view.current_nodes[-1]
		ns = {}
		path = make_relative_path(src, element, FALSE, ns)
		self.view.may_record(["do_search", path, ns, FALSE])
		self.view.may_record(["attribute", attrib])
	
	def show_menu(self, bev):
		items = [
			('Search', self.show_search),
			('Text search', self.show_text_search),
			('Global', self.show_global),
			(None, None),
			('Yank attributes', self.show_yank_attribs),
			('Paste attributes', lambda self = self: self.view.may_record(['paste_attribs'])),
			('Yank attrib value', self.show_yank_attrib),
			(None, None),
			('Cut', lambda self = self: self.view.may_record(['delete_node'])),
			('Paste (replace)', lambda self = self: self.view.may_record(['put_replace'])),
			('Paste (inside)', lambda self = self: self.view.may_record(['put_as_child'])),
			('Paste (before)', lambda self = self: self.view.may_record(['put_before'])),
			('Paste (after)', lambda self = self: self.view.may_record(['put_after'])),
			(None, None),
			('Substitute', self.show_subst),
			('Process', self.show_pipe),
			(None, None),
			('Question', self.show_ask),
			('Fail', lambda self = self: self.view.may_record(['fail'])),
			(None, None),
			('Undo', lambda self = self: self.view.may_record(['undo'])),
			('Redo', lambda self = self: self.view.may_record(['redo'])),
			('Enter', self.view.enter),
			('Leave', self.view.leave),
			('Close Window', self.window.destroy),
			]
		Menu(items).popup(bev.button, bev.time)
	
	def playback(self, macro, map):
		"Called when the user clicks on a macro button."
		Exec.exec_state.clean()
		if map:
			self.view.may_record(['map', macro.uri])
		else:
			self.view.may_record(['play', macro.uri])

	def show_ask(self):
		def do_ask(q, self = self):
			action = ["ask", q]
			self.view.may_record(action)
		GetArg('Ask:', do_ask, ('Question:',))

	def show_subst(self):
		def do_subst(args, self = self):
			action = ["subst", args[0], args[1]]
			self.view.may_record(action)
		GetArg('Substitute:', do_subst, ('Replace:', 'With:'))

	def show_edit(self):
		edit_node(self, self.view.current)

	def show_del_attrib(self):
		def do_attrib(attrib, self = self):
			action = ["del_attrib", attrib]
			self.view.may_record(action)
		GetArg('Delete attribute:', do_attrib, ['Name:'])

	def show_yank_attribs(self):
		def do_attrib(attrib, self = self):
			action = ["yank_attribs", attrib]
			self.view.may_record(action)
		GetArg('Yank attribute:', do_attrib, ['Name:'], message = 'Blank for all...')

	def show_yank_attrib(self):
		def do_attrib(attrib, self = self):
			action = ["yank_value", attrib]
			self.view.may_record(action)
		GetArg('Yank value of attribute:', do_attrib, ['Name:'])

	def show_attrib(self):
		def do_attrib(args, self = self):
			action = ["attribute", args]
			self.view.may_record(action)
		GetArg('Select attribute:', do_attrib, ['Name:'])

	def show_pipe(self):
		def do_pipe(expr, self = self):
			action = ["python", expr]
			self.view.may_record(action)
		GetArg('Python expression:', do_pipe, ['Eval:'], "'x' is the old text...")

	def show_global(self):
		def do_global(pattern, self = self):
			action = ["do_global", pattern]
			self.view.may_record(action)
		GetArg('Global:', do_global, ['Pattern:'], 'Perform next action on all nodes matching')

	def show_text_search(self):
		def do_text_search(pattern, self = self):
			action = ["do_text_search", pattern]
			self.view.may_record(action)
		GetArg('Search for:', do_text_search, ['Text pattern:'])

	def show_search(self):
		def do_search(pattern, self = self):
			action = ["do_search", pattern]
			self.view.may_record(action)
		GetArg('Search for:', do_search, ['XPath:'])

	def new_element(self):
		cur = self.view.current
		if cur.nodeType == Node.TEXT_NODE:
			return self.view.model.doc.createElement( cur.parentNode.nodeName)
		return self.view.model.doc.createElement(cur.nodeName)
	
	def insert_element(self):
		"Insert element"
		new = self.new_element()
		edit_node(self, new, "ie")
		return new

	def append_element(self):
		"Append element"
		new = self.new_element()
		edit_node(self, new, "ae")
		return new

	def open_element(self):
		"Open element"
		new = self.new_element()
		edit_node(self, new, "oe")
		
	def insert_text(self):
		"Insert text"
		new = self.view.model.doc.createTextNode('')
		edit_node(self, new, "it")

	def append_text(self):
		"Append text"
		new = self.view.model.doc.createTextNode('')
		edit_node(self, new, "at")

	def open_text(self):
		"Open text"
		new = self.view.model.doc.createTextNode('')
		edit_node(self, new, "ot")

	key_to_action = {
		# Motions
		Up	: ["move_prev_sib"],
		Down	: ["move_next_sib"],
		Left	: ["move_left"],
		Right	: ["move_right"],
		
		Home	: ["move_home"],
		End	: ["move_end"],
		
		greater	: ["enter"],
		less	: ["leave"],
		
		#Prior	: ["move_prev_sib"],
		#Next	: ["move_next_sib"],

		t	: show_text_search,
		slash	: show_search,
		ord('#'): show_global,
		#n	: ["search_next"],

		# Tests

		question: show_ask,
		ord('='): ["compare"],

		# Changes
		I	: insert_element,
		A	: append_element,
		O	: open_element,
		
		i	: insert_text,
		a	: append_text,
		o	: open_text,

		y	: ["yank"],
		Y	: show_yank_attribs,
		P	: ["put_before"],
		p	: ["put_after"],
		bracketright : ["put_as_child"],
		R	: ["put_replace"],

		ord('^'): ["suck"],

		Tab	: show_edit,
		at	: show_attrib,
		exclam	: show_pipe,
		s	: show_subst,

		x	: ["delete_node"],
		X	: show_del_attrib,

		# Undo/redo
		u	: ["undo"],
		r	: ["redo"],
	}
