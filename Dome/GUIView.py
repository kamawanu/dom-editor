from __future__ import nested_scopes

from gtk import *
from GDK import *
from xml.dom import Node
import string
from loader import make_xds_loader

from rox.support import report_exception

from View import View
from Display import Display
from Beep import Beep
from GetArg import GetArg
from Path import make_relative_path

from rox.Menu import Menu

menu = Menu('Dome', 'main', [
		('/File', None, '<Branch>', ''),
		('/File/Save', 'menu_save', '', 'F3'),
		('/File/Blank document', 'do_blank_all', '', '<Ctrl>N'),

		('/Edit', None, '<Branch>', ''),
		('/Edit/Yank attributes', 'do_yank_attributes', '', ''),
		('/Edit/Paste attributes', 'do_paste_attribs', '', ''),
		('/Edit/Yank attrib value', 'do_yank_value', '', ''),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Cut', 'do_delete_node', '', 'x'),
		('/Edit/Delete', 'do_delete_node_no_clipboard', '', '<Ctrl>X'),
		('/Edit/Shallow cut', 'do_delete_shallow', '', '<Shift>X'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Yank', 'do_yank', '', 'y'),
		('/Edit/Shallow yank', 'do_shallow_yank', '', '<Shift>Y'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Paste (replace)','do_put_replace', '', '<Shift>R'),
		('/Edit/Paste (inside)', 'do_put_as_child', '', 'bracketright'),
		('/Edit/Paste (before)', 'do_put_before', '', '<Shift>P'),
		('/Edit/Paste (after)', 'do_put_after', '', 'p'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Edit value', 'toggle_edit', '', 'Return'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Undo', 'do_undo', '', 'u'),
		('/Edit/Redo', 'do_redo', '', '<Ctrl>R'),

		('/Move', None, '<Branch>', ''),
		('/Move/XPath search', 'menu_show_search', '', 'slash'),
		('/Move/Text search', 'menu_show_text_search', '', 'T'),
		('/Move/Enter', 'do_enter', '', '<Shift>greater'),
		('/Move/Leave', 'do_leave', '', '<Shift>less'),
		
		('/Move/Root node', 'move_home', '', 'Home'),
		('/Move/Previous sibling', 'move_prev_sib', '', 'Up'),
		('/Move/Next sibling', 'move_next_sib', '', 'Down'),
		('/Move/Parent', 'move_left', '', 'Left'),
		('/Move/First child', 'move_right', '', 'Right'),
		('/Move/Last child', 'move_end', '', 'End'),

		('/Move/To attribute', 'menu_select_attrib', '', 'At'),

		('/Select', None, '<Branch>', ''),
		('/Select/By XPath', 'menu_show_global', '', 'numbersign'),
		('/Select/Duplicate Siblings', 'do_select_dups', '', ''),
		('/Select/To Mark', 'do_select_marked', '', 'minus'),

		('/Mark', None, '<Branch>', ''),
		('/Mark/Mark Selection', 'do_mark_selection', '', 'm'),
		('/Mark/Switch with Selection', 'do_mark_switch', '', 'comma'),
		('/Mark/Clear Mark', 'do_clear_mark', '', ''),

		('/Network', None, '<Branch>', ''),
		('/Network/HTTP GET', 'do_suck', '', '<Shift>asciicircum'),
		('/Network/HTTP POST', 'do_http_post', '', ''),
		('/Network/Send SOAP message', 'do_soap_send', '', ''),

		('/Create', None, '<Branch>', ''),
		('/Create/Insert element', 'menu_insert_element', '', '<Shift>I'),
		('/Create/Append element', 'menu_append_element', '', '<Shift>A'),
		('/Create/Open element', 'menu_open_element', '', '<Shift>O'),
		('/Create/Open element at end', 'menu_open_element_end', '', '<Shift>E'),

		('/Create/', '', '', '<separator>'),

		('/Create/Insert text node', 'menu_insert_text', '', 'I'),
		('/Create/Append text node', 'menu_append_text', '', 'A'),
		('/Create/Open text node', 'menu_open_text', '', 'O'),
		('/Create/Open text node at end', 'menu_open_text_end', '', 'E'),

		('/Create/', '', '', '<separator>'),

		('/Create/Attribute', 'menu_show_add_attrib', '', '<Shift>plus'),

		('/Process', None, '<Branch>', ''),
		('/Process/Substitute', 'menu_show_subst', '', 's'),
		('/Process/Python expression', 'menu_show_pipe', '', '<Shift>exclam'),
		('/Process/Normalise', 'do_normalise', '', ''),
		('/Process/Remove default namespaces', 'do_remove_ns', '', 'r'),
		('/Process/Comment to text', 'do_convert_to_text', '', ''),

		('/Program', None, '<Branch>', ''),
		('/Program/Input', 'menu_show_ask', '', 'question'),
		('/Program/Compare', 'do_compare', '', 'equal'),
		('/Program/Fail', 'do_fail', '', ''),
		('/Program/Pass', 'do_pass', '', ''),
		('/Program/Repeat last', 'do_again', '', 'dot'),

		('/View', None, '<Branch>', ''),
		('/View/Toggle hidden', 'do_toggle_hidden', '', '<Ctrl>H'),
		('/View/Show as HTML', 'do_show_html', '', ''),
		('/View/Show as canvas', 'do_show_canvas', '', ''),
		('/View/Close Window', 'menu_close_window', '', '<Ctrl>Q'),
		])

def make_do(action):
	return lambda(self): self.view.may_record([action])

class GUIView(Display):
	def __init__(self, window, view):
		Display.__init__(self, window, view)
		window.connect('key-press-event', self.key_press)
		self.window = window
		self.cursor_node = None
		make_xds_loader(self, self)
		self.update_state()

		menu.attach(window, self)
	
	def update_state(self):
		if self.view.rec_point:
			state = "(recording)"
		elif self.view.idle_cb or self.view.op_in_progress:
			state = "(playing)"
		else:
			state = ""
		self.window.set_state(state)
		self.do_update_now()

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
		if kev.keyval == Up:
			self.view.may_record(['move_prev_sib'])
		elif kev.keyval == Down:
			self.view.may_record(['move_next_sib'])
		elif kev.keyval == Left:
			self.view.may_record(['move_left'])
		elif kev.keyval == Right:
			self.view.may_record(['move_right'])
		elif kev.keyval == KP_Add:
			self.menu_show_add_attrib()
		elif kev.keyval == Tab:
			self.toggle_edit()
		else:
			return 0
		widget.emit_stop_by_name('key-press-event')
		return 1

	def node_clicked(self, node, bev):
		print "Clicked", node.namespaceURI, node.localName
		if node:
			if bev.type == BUTTON_PRESS:
				if len(self.view.current_nodes) == 0:
					src = self.view.root
				else:
					src = self.view.current_nodes[-1]
				shift = bev.state & SHIFT_MASK
				add = bev.state & CONTROL_MASK
				select_region = shift and node.nodeType == Node.ELEMENT_NODE
				lit = shift and not select_region
					
				ns = {}
				path = make_relative_path(src, node, lit, ns)
				if path == '.' and self.view.current_nodes and not self.view.current_attrib:
					return
				if select_region:
					self.view.may_record(["select_region", path, ns])
				else:
					self.view.may_record(["do_search", path, ns, add])
			else:
				self.view.may_record(["toggle_hidden"])

	def attrib_clicked(self, element, attrib, event):
		if len(self.view.current_nodes) == 0:
			src = self.view.root
		else:
			src = self.view.current_nodes[-1]
		ns = {}

		print "attrib_clicked", attrib, attrib.namespaceURI, attrib.localName
		path = make_relative_path(src, element, FALSE, ns)
		if path != '.':
			self.view.may_record(["do_search", path, ns, FALSE])
		self.view.may_record(["attribute", attrib.namespaceURI, attrib.localName])
	
	def menu_save(self):
		self.window.save()
	
	def show_menu(self, bev):
		menu.popup(self, bev)
	
	def playback(self, macro, map):
		"Called when the user clicks on a macro button."
		Exec.exec_state.clean()
		if map:
			self.view.may_record(['map', macro.uri])
		else:
			self.view.may_record(['play', macro.uri])

	def menu_show_ask(self):
		def do_ask(q, self = self):
			action = ["ask", q]
			self.view.may_record(action)
		GetArg('Input:', do_ask, ('Prompt:',))

	def menu_show_subst(self):
		def do_subst(args, self = self):
			action = ["subst", args[0], args[1]]
			self.view.may_record(action)
		GetArg('Substitute:', do_subst, ('Replace:', 'With:'))
	
	def move_from(self, old = []):
		self.hide_editbox()
		Display.move_from(self, old)
	
	def hide_editbox(self):
		if self.cursor_node:
			if self.cursor_attrib:
				self.cursor_hidden_text.set(text = '%s=%s' %
					(self.cursor_attrib.name, self.cursor_attrib.value))
			self.cursor_hidden_text.show()
			self.auto_highlight(self.cursor_node)
			self.cursor_node = None
			self.edit_box_item.destroy()

	def show_editbox(self):
		"Edit the current node/attribute"
		self.do_update_now()

		if self.cursor_node:
			self.hide_editbox()

		if not self.visible:
			raise Exception("Can't edit while display is hidden!")

		self.cursor_node = self.view.current_nodes[0]
		group = self.node_to_group[self.cursor_node]
		self.cursor_attrib = self.view.current_attrib

		self.highlight(group, FALSE)

		if self.cursor_attrib:
			group = group.attrib_to_group[self.cursor_attrib]

		self.cursor_hidden_text = group.text
		if not self.cursor_attrib:
			# Don't hide for attributes, so we can still see the name
			group.text.hide()
		else:
			group.text.set(text = str(self.cursor_attrib.name) + '=')
			
		lx, ly, hx, hy = group.text.get_bounds()
		x, y = group.i2w(lx, ly)

		eb = GtkText()
		self.edit_box = eb
		m = 3
		s = eb.get_style().copy()
		s.font = load_font('fixed')
		if self.cursor_attrib:
			name_width = s.font.measure(self.cursor_attrib.name + '=') + 1
		else:
			name_width = 0
		self.edit_box_item = self.root().add('widget', widget = eb,
						x = x - m + name_width, y = y - m,
						anchor = ANCHOR_NW)
		eb.set_style(s)

		eb.set_editable(TRUE)
		eb.insert_defaults(self.get_edit_text())
		eb.connect('changed', self.eb_changed)
		eb.connect('key_press_event', self.eb_key)
		eb.set_line_wrap(FALSE)
		self.size_eb()
		eb.grab_focus()
		eb.select_region(0, -1)
		eb.show()
	
	def get_edit_text(self):
		node = self.cursor_node
		if node.nodeType == Node.ELEMENT_NODE:
			if self.cursor_attrib:
				return str(self.cursor_attrib.value)
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

	def menu_select_attrib(self):
		def do_attrib(name, self = self):
			if ':' in name:
				(prefix, localName) = string.split(name, ':', 1)
			else:
				(prefix, localName) = (None, name)
			namespaceURI = self.view.model.prefix_to_namespace(self.view.get_current(), prefix)
			action = ["attribute", namespaceURI, localName]
			self.view.may_record(action)
		GetArg('Select attribute:', do_attrib, ['Name:'])

	def menu_show_add_attrib(self):
		def do_it(name, self = self):
			action = ["add_attrib", "UNUSED", name]
			self.view.may_record(action)
		GetArg('Create attribute:', do_it, ['Name:'])

	def menu_show_pipe(self):
		def do_pipe(expr, self = self):
			action = ["python", expr]
			self.view.may_record(action)
		GetArg('Python expression:', do_pipe, ['Eval:'], "'x' is the old text...")

	def menu_show_global(self):
		def do_global(pattern, self = self):
			action = ["do_global", pattern]
			self.view.may_record(action)
		GetArg('Global:', do_global, ['Pattern:'],
			'(@CURRENT@ is the current node\'s value)\n' +
			'Perform next action on all nodes matching')

	def menu_show_text_search(self):
		def do_text_search(pattern, self = self):
			action = ["do_text_search", pattern]
			self.view.may_record(action)
		GetArg('Search for:', do_text_search, ['Text pattern:'],
			'(@CURRENT@ is the current node\'s value)\n')

	def menu_show_search(self):
		def do_search(pattern, self = self):
			action = ["do_search", pattern]
			self.view.may_record(action)
		GetArg('Search for:',
			do_search, ['XPath:'],
			'(@CURRENT@ is the current node\'s value)')

	def show_add_box(self, action):
		if action[0] == 'i':
			text = 'Insert'
		elif action[0] == 'a':
			text = 'Append'
		elif action[0] == 'o':
			text = 'Open'
		elif action[0] == 'e':
			text = 'Open at end'
		else:
			assert 0
		if action[1] == 'e':
			text += ' element'
			prompt = 'Node name'
		elif action[1] == 't':
			text += ' text'
			prompt = 'Text'
		else:
			assert 0

		def cb(value):
			self.view.may_record(['add_node', action, value])
		GetArg('Add node', cb, [prompt], text)
	
	def new_name(self):
		cur = self.view.get_current()
		if cur.nodeType == Node.ELEMENT_NODE:
			return cur.nodeName
		return cur.parentNode.nodeName
	
	def menu_insert_element(self):
		"Insert element"
		self.show_add_box('ie')

	def menu_append_element(self):
		"Append element"
		self.show_add_box('ae')

	def menu_open_element(self):
		"Open element"
		self.show_add_box('oe')
		
	def menu_open_element_end(self):
		"Open element at end"
		self.show_add_box('ee')
		
	def menu_insert_text(self):
		"Insert text"
		self.show_add_box('it')

	def menu_append_text(self):
		"Append text"
		self.show_add_box('at')

	def menu_open_text(self):
		"Open text"
		self.show_add_box('ot')

	def menu_open_text_end(self):
		"Open text at end"
		self.show_add_box('et')

	def menu_close_window(self):
		self.window.destroy()

	do_blank_all = make_do('blank_all')
	do_enter = make_do('enter')
	do_leave = make_do('leave')
	do_suck = make_do('suck')
	do_http_post = make_do('http_post')
	do_soap_send = make_do('soap_send')
	do_select_dups = make_do('select_dups')
	do_paste_attribs = make_do('paste_attribs')
	do_yank_value = make_do('yank_value')
	do_yank_attributes = make_do('yank_attribs')
	do_delete_node = make_do('delete_node')
	do_delete_node_no_clipboard = make_do('delete_node_no_clipboard')
	do_delete_shallow = make_do('delete_shallow')
	do_yank = make_do('yank')
	do_shallow_yank = make_do('shallow_yank')
	do_put_replace = make_do('put_replace')
	do_put_as_child = make_do('put_as_child')
	do_put_before = make_do('put_before')
	do_put_after = make_do('put_after')
	do_undo = make_do('undo')
	do_redo = make_do('redo')
	do_fail = make_do('fail')
	do_pass = make_do('do_pass')
	do_toggle_hidden = make_do('toggle_hidden')
	do_show_html = make_do('show_html')
	do_show_canvas = make_do('show_canvas')
	do_compare = make_do('compare')
	do_again = make_do('again')
	do_normalise = make_do('normalise')
	do_convert_to_text = make_do('convert_to_text')
	do_remove_ns = make_do('remove_ns')

	do_clear_mark = make_do('clear_mark')
	do_mark_switch = make_do('mark_switch')
	do_mark_selection = make_do('mark_selection')
	do_select_marked = make_do('select_marked_region')

	move_home = make_do('move_home')
	move_end = make_do('move_end')
	move_left = make_do('move_left')
	move_right = make_do('move_right')
	move_next_sib = make_do('move_next_sib')
	move_prev_sib = make_do('move_prev_sib')
