from gtk import *
from GDK import *
from xml.dom import Node
import string

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
		self.cursor_node = None

	def key_press(self, widget, kev):
		if self.cursor_node:
			return 1
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

		if key == F3:
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
		self.view.may_record(["attribute", attrib.namespaceURI, attrib.localName])
	
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
	
	def move_from(self, old = []):
		self.hide_editbox()
		Display.move_from(self, old)
	
	def hide_editbox(self):
		if self.cursor_node:
			group = self.node_to_group[self.cursor_node]
			self.cursor_hidden_text.show()
			self.hightlight(group, self.cursor_node in self.view.current_nodes)
			self.cursor_node = None
			self.edit_box_item.destroy()

	def show_editbox(self):
		"Edit the current node/attribute"
		if self.cursor_node:
			self.hide_editbox()
		node = self.view.current

		group = self.node_to_group[node]
		self.cursor_node = node
		self.cursor_attrib = self.view.current_attrib

		self.hightlight(group, FALSE)

		if self.cursor_attrib:
			group = group.attrib_to_group[self.cursor_attrib]

		self.cursor_hidden_text = group.text
		group.text.hide()
			
		lx, ly, hx, hy = group.text.get_bounds()
		x, y = group.i2w(lx, ly)

		eb = GtkText()
		self.edit_box = eb
		m = 3
		self.edit_box_item = self.root().add('widget', widget = eb,
						x = x - m, y = y - m,
						anchor = ANCHOR_NW)
		s = eb.get_style().copy()
		s.font = load_font('fixed')
		eb.set_style(s)

		eb.set_editable(TRUE)
		eb.insert_defaults(self.get_edit_text())
		eb.connect('changed', self.eb_changed)
		eb.connect('key_press_event', self.eb_key)
		eb.set_line_wrap(FALSE)
		self.size_eb()
		eb.grab_focus()
		eb.show()
	
	def get_edit_text(self):
		node = self.cursor_node
		if node.nodeType == Node.ELEMENT_NODE:
			if self.cursor_attrib:
				a = node.getAttributeNode(self.cursor_attrib)
				return "%s=%s" % (str(a.name), str(a.value))
			return node.nodeName
		else:
			return node.nodeValue
	
	def eb_key(self, eb, kev):
		key = kev.keyval
		if key == KP_Enter:
			key = Return
		if key == Escape:
			self.hide_editbox()
		elif key == Return and kev.state & CONTROL_MASK:
			eb.insert_defaults('\n')
			self.size_eb()
		elif key == Tab or key == Return:
			text = eb.get_chars(0, -1)
			if text != self.get_edit_text():
				self.commit_edit(text)
			self.hide_editbox()
		return 1

	def commit_edit(self, new):
		if self.cursor_attrib:
			self.view.may_record(['set_attrib', new])
		else:
			self.view.may_record(['change_node', new])
	
	def eb_changed(self, eb):
		self.size_eb()
	
	def size_eb(self):
		text = self.edit_box.get_chars(0, -1)
		lines = string.split(text, '\n')
		w = 0
		font = self.edit_box.get_style().font
		rh = font.ascent + font.descent
		for l in lines:
			if l[-1:] == ' ':
				l += ' '
			lw = font.measure(l)
			if lw > w:
				w = lw
		width = w + 18
		height = len(lines) * rh + 8
		self.edit_box_item.set(width = width, height = height)

	def toggle_edit(self):
		if self.cursor_node:
			self.hide_editbox()
		else:
			self.show_editbox()

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
		def do_attrib(name, self = self):
			if self.view.current.hasAttribute(name):
				action = ["attribute", name]
				self.view.may_record(action)
			else:
				def do_create(value, self = self, name = name):
					action = ["set_attrib", ("%s=%s" % (name, value))]
					print action
					self.view.may_record(action)
				GetArg('Create attribute:', do_create, ['%s = ' % name])
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

		Tab	: toggle_edit,
		Return	: toggle_edit,
		at	: show_attrib,
		exclam	: show_pipe,
		s	: show_subst,

		x	: ["delete_node"],
		X	: show_del_attrib,

		# Undo/redo
		u	: ["undo"],
		r	: ["redo"],
	}
