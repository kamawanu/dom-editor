from gtk import *
from GDK import *
from xml.dom import Node
import string
from loader import make_xds_loader

from support import report_exception

from View import View
from Display import Display
from Beep import Beep
from Menu import Menu
from GetArg import GetArg
from Path import make_relative_path

class GUIView(Display):
	def __init__(self, window, view):
		Display.__init__(self, window, view)
		window.connect('key-press-event', self.key_press)
		self.cursor_node = None
		make_xds_loader(self, self)

	def load_file(self, path):
		if path[-5:] == '.html':
			self.view.load_html(path)
		else:
			self.view.load_xml(path)
		if self.view.root == self.view.model.get_root():
			self.window.uri = path
			self.window.update_title()

	def load_data(self, data):
		report_error("Can only load files for now - sorry")
	
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
			if bev.type == BUTTON_PRESS:
				if len(self.view.current_nodes) == 0:
					src = self.view.root
				else:
					src = self.view.current_nodes[-1]
				lit = bev.state & SHIFT_MASK
				add = bev.state & CONTROL_MASK
				ns = {}
				path = make_relative_path(src, node, lit, ns)
				if path == '.' and self.view.current_nodes and not self.view.current_attrib:
					return
				self.view.may_record(["do_search", path, ns, add])
			else:
				self.view.may_record(["toggle_hidden"])

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
		def do(action, self = self):
			return lambda self = self, action = action: self.view.may_record([action])

		items = [
			('Search', self.show_search),
			('Text search', self.show_text_search),
			('Global', self.show_global),
			('HTTP suck', do('suck')),
			(None, None),
			('Add attribute', self.show_add_attrib),
			('Yank attributes', self.show_yank_attribs),
			('Paste attributes', do('paste_attribs')),
			('Yank attrib value', do('yank_value')),
			(None, None),
			('Cut', do('delete_node')),
			('Yank', do('yank')),
			('Shallow yank', do('shallow_yank')),
			('Paste (replace)', do('put_replace')),
			('Paste (inside)', do('put_as_child')),
			('Paste (before)', do('put_before')),
			('Paste (after)', do('put_after')),
			(None, None),
			('Substitute', self.show_subst),
			('Process', self.show_pipe),
			(None, None),
			('Input', self.show_ask),
			('Fail', do('fail')),
			(None, None),
			('Undo', do('undo')),
			('Redo', do('redo')),
			('Enter', do('enter')),
			('Leave', do('leave')),
			('Show as HTML', do('show_html')),
			('Show as canvas', do('show_canvas')),
			('Send SOAP message', do('soap_send')),
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
		GetArg('Input:', do_ask, ('Prompt:',))

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
			self.auto_hightlight(self.cursor_node)
			self.cursor_node = None
			self.edit_box_item.destroy()

	def show_editbox(self):
		"Edit the current node/attribute"
		self.do_update_now()

		if self.cursor_node:
			self.hide_editbox()

		self.cursor_node = self.view.get_current()
		group = self.node_to_group[self.cursor_node]
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
				name, value = (self.cursor_attrib.name, self.cursor_attrib.value)
				return "%s=%s" % (str(name), str(value))
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
			try:
				if text != self.get_edit_text():
					self.commit_edit(text)
			finally:
				self.hide_editbox()
		return 1

	def commit_edit(self, new):
		if self.cursor_attrib:
			name, value = string.split(new, '=', 1)
			self.view.may_record(['set_attrib', value])
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
			if ':' in name:
				(prefix, localName) = string.split(name, ':', 1)
			else:
				(prefix, localName) = ('', name)
			namespaceURI = self.view.model.prefix_to_namespace(self.view.get_current(), prefix)
			action = ["attribute", namespaceURI, localName]
			self.view.may_record(action)
		GetArg('Select attribute:', do_attrib, ['Name:'])

	def show_add_attrib(self):
		def do_it(name, self = self):
			if ':' in name:
				(prefix, localName) = string.split(name, ':', 1)
			else:
				(prefix, localName) = ('', name)
			namespaceURI = self.view.model.prefix_to_namespace(self.view.get_current(), prefix)
			action = ["add_attrib", namespaceURI, name]
			self.view.may_record(action)
		GetArg('Create attribute:', do_it, ['Name:'])

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

	def new_name(self):
		cur = self.view.get_current()
		if cur.nodeType == Node.ELEMENT_NODE:
			return cur.nodeName
		return cur.parentNode.nodeName
	
	def insert_element(self):
		"Insert element"
		self.view.may_record(['add_node', 'ie', self.new_name()])
		self.show_editbox()

	def append_element(self):
		"Append element"
		self.view.may_record(['add_node', 'ae', self.new_name()])
		self.show_editbox()

	def open_element(self):
		"Open element"
		self.view.may_record(['add_node', 'oe', self.new_name()])
		self.show_editbox()
		
	def insert_text(self):
		"Insert text"
		self.view.may_record(['add_node', 'it', ''])
		self.show_editbox()

	def append_text(self):
		"Append text"
		self.view.may_record(['add_node', 'at', ''])
		self.show_editbox()

	def open_text(self):
		"Open text"
		self.view.may_record(['add_node', 'ot', ''])
		self.show_editbox()

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
		plus	: show_add_attrib,
		KP_Add	: show_add_attrib,
		exclam	: show_pipe,
		s	: show_subst,

		x	: ["delete_node"],
		X	: show_del_attrib,

		ord('.'): ["again"],

		# Undo/redo
		u	: ["undo"],
		r	: ["redo"],
	}
