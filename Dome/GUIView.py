from xml.dom import Node
from rox.loading import XDSLoader

import rox
from rox import g, TRUE, FALSE
keysyms = g.keysyms

from View import View
from Display2 import Display
from Beep import Beep
from GetArg import GetArg
from Path import make_relative_path

from rox.Menu import Menu

menu = Menu('main', [
		('/File', None, '<Branch>', ''),
		('/File/Save', 'menu_save', '', '<Ctrl>S'),
		('/File/Blank document', 'do_blank_all', '', '<Ctrl>N'),
		('/File/Clear undo buffer', 'menu_clear_undo', '', ''),

		('/Edit', None, '<Branch>', ''),
		('/Edit/Copy attributes', 'do_yank_attributes', '', ''),
		('/Edit/Paste attributes', 'do_paste_attribs', '', ''),
		('/Edit/Copy attrib value', 'do_yank_value', '', ''),
		('/Edit/Rename attribute', 'menu_rename_attr', '', ''),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Cut', 'do_delete_node', '', '<Ctrl>X'),
		('/Edit/Delete', 'do_delete_node_no_clipboard', '', ''),
		('/Edit/Shallow cut', 'do_delete_shallow', '', '<Shift>X'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Copy', 'do_yank', '', '<Ctrl>C'),
		('/Edit/Shallow copy', 'do_shallow_yank', '', '<Shift>Y'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Paste (replace)','do_put_replace', '', '<Ctrl>V'),
		('/Edit/Paste (inside)', 'do_put_as_child', '', 'bracketright'),
		('/Edit/Paste (before)', 'do_put_before', '', '<Shift>P'),
		('/Edit/Paste (after)', 'do_put_after', '', 'p'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Edit value', 'toggle_edit', '', 'Return'),
		('/Edit/', '', '', '<separator>'),
		('/Edit/Undo', 'do_undo', '', '<Ctrl>Z'),
		('/Edit/Redo', 'do_redo', '', '<Ctrl>Y'),

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
		('/Select/Child Nodes', 'do_select_children', '', 'asterisk'),

		('/Mark', None, '<Branch>', ''),
		('/Mark/Mark Selection', 'do_mark_selection', '', 'm'),
		('/Mark/Switch with Selection', 'do_mark_switch', '', 'comma'),
		('/Mark/Clear Mark', 'do_clear_mark', '', ''),

		('/Network', None, '<Branch>', ''),
		('/Network/HTTP GET', 'do_suck', '', '<Shift>asciicircum'),
		('/Network/HTTP POST', 'do_http_post', '', ''),
		('/Network/Send SOAP message', 'do_soap_send', '', ''),

		('/Create', None, '<Branch>', ''),
		('/Create/Insert node', 'menu_insert_element', '', 'I'),
		('/Create/Append node', 'menu_append_element', '', 'A'),
		('/Create/Open node inside', 'menu_open_element', '', 'O'),
		('/Create/Open node at end', 'menu_open_element_end', '', 'E'),

		('/Process', None, '<Branch>', ''),
		('/Process/Substitute', 'menu_show_subst', '', 's'),
		('/Process/Python expression', 'menu_show_pipe', '', '<Shift>exclam'),
		('/Process/XPath expression', 'menu_show_xpath', '', ''),
		('/Process/Normalise', 'do_normalise', '', ''),
		('/Process/Remove default namespaces', 'do_remove_ns', '', 'r'),
		('/Process/Convert to text', 'do_convert_to_text', '', ''),
		('/Process/Convert to comment', 'do_convert_to_comment', '', ''),
		('/Process/Convert to element', 'do_convert_to_element', '', ''),

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
		('/View/Show namespaces', 'show_namespaces', '', '<Ctrl>;'),
		('/View/Close Window', 'menu_close_window', '', '<Ctrl>Q'),

		#('/Options...', 'menu_options', '', '<Ctrl>O'),
		])

def make_do(action):
	return lambda(self): self.view.may_record([action])

class GUIView(Display, XDSLoader):
	def __init__(self, window, view):
		Display.__init__(self, window, view)
		XDSLoader.__init__(self, ['application/x-dome', 'text/xml',
					  'application/xml'])
		window.connect('key-press-event', self.key_press)
		self.cursor_node = None
		self.edit_dialog = None
		self.update_state()

		menu.attach(window, self)
	
	def destroyed(self, widget):
		print "GUIView destroyed!"
		Display.destroyed(self, widget)
		del self.cursor_node
	
	def update_state(self):
		if self.view.rec_point:
			state = "(recording)"
		elif self.view.idle_cb or self.view.op_in_progress:
			state = "(playing)"
		else:
			state = ""
		self.parent_window.set_state(state)
		self.do_update_now()

	def xds_load_from_stream(self, path, type, stream):
		if not path:
			raise Exception('Can only load from files... sorry!')
		if path.endswith('.html'):
			self.view.load_html(path)
		else:
			self.view.load_xml(path)
		if self.view.root == self.view.model.get_root():
			self.parent_window.uri = path
			self.parent_window.update_title()

	def key_press(self, widget, kev):
		focus = widget.focus_widget
		if focus and focus is not widget and focus.get_toplevel() is widget:
			if focus.event(kev):
				return TRUE	# Handled

		if self.cursor_node:
			return 0
		if kev.keyval == keysyms.Up:
			self.view.may_record(['move_prev_sib'])
		elif kev.keyval == keysyms.Down:
			self.view.may_record(['move_next_sib'])
		elif kev.keyval == keysyms.Left:
			self.view.may_record(['move_left'])
		elif kev.keyval == keysyms.Right:
			self.view.may_record(['move_right'])
		elif kev.keyval == keysyms.KP_Add:
			self.menu_show_add_attrib()
		elif kev.keyval == keysyms.Tab:
			self.toggle_edit()
		else:
			return 0
		return 1

	def node_clicked(self, node, bev):
		print "Clicked", node.namespaceURI, node.localName
		if node:
			if bev.type == g.gdk.BUTTON_PRESS:
				if len(self.view.current_nodes) == 0:
					src = self.view.root
				else:
					src = self.view.current_nodes[-1]
				shift = bev.state & g.gdk.SHIFT_MASK
				add = bev.state & g.gdk.CONTROL_MASK
				select_region = shift and node.nodeType == Node.ELEMENT_NODE
				lit = shift and not select_region
					
				path = make_relative_path(src, node, lit, self.view.model.namespaces)
				if path == '.' and self.view.current_nodes and not self.view.current_attrib:
					return
				if select_region:
					self.view.may_record(["select_region", path, "unused"])
				else:
					self.view.may_record(["do_search", path, "unused", add])
			else:
				self.view.may_record(["toggle_hidden"])

	def attrib_clicked(self, element, attrib, event):
		if len(self.view.current_nodes) == 0:
			src = self.view.root
		else:
			src = self.view.current_nodes[-1]

		print "attrib_clicked", attrib, attrib.namespaceURI, attrib.localName
		path = make_relative_path(src, element, FALSE, self.view.model.namespaces)
		if path != '.':
			self.view.may_record(["do_search", path, "unused", FALSE])
		self.view.may_record(["attribute", attrib.namespaceURI, attrib.localName])
	
	def menu_save(self):
		self.parent_window.save()
	
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
	
	def show_namespaces(self):
		import Namespaces
		Namespaces.GUI(self.view.model).show()
	
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

	def toggle_edit(self):
		node = self.view.current_nodes[0]
		attrib = self.view.current_attrib

		if self.edit_dialog:
			self.edit_dialog.destroy()
		self.edit_dialog = rox.Dialog()
		eb = self.edit_dialog

		if node.nodeType == Node.ELEMENT_NODE:
			if attrib:
				text = unicode(attrib.value)
			else:
				text = node.nodeName
			entry = g.Entry()
			entry.set_text(text)
			entry.set_activates_default(True)
			def get_text(): return entry.get_text()
		else:
			text = node.nodeValue
			entry = g.TextView()
			buffer = entry.get_buffer()
			buffer.insert_at_cursor(text)
			entry.set_size_request(400, 200)

			def get_text():
				start = buffer.get_start_iter()
				end = buffer.get_end_iter()
				return buffer.get_text(start, end, True)
		eb.vbox.pack_start(entry, TRUE, FALSE, 0)

		eb.add_button(g.STOCK_CANCEL, g.RESPONSE_CANCEL)
		eb.add_button(g.STOCK_APPLY, g.RESPONSE_OK)
		eb.set_default_response(g.RESPONSE_OK)
		entry.grab_focus()
		def destroy(eb):
			self.edit_dialog = None
		eb.connect('destroy', destroy)
		def response(eb, resp):
			if resp == g.RESPONSE_CANCEL:
				eb.destroy()
			elif resp == g.RESPONSE_OK:
				new = get_text()
				if new != text:
					if attrib:
						self.view.may_record(['set_attrib', new])
					else:
						self.view.may_record(['change_node', new])
				eb.destroy()
		eb.connect('response', response)

		eb.show_all()

	def menu_select_attrib(self):
		def do_attrib(name):
			if ':' in name:
				(prefix, localName) = name.split(':', 1)
				namespaceURI = self.view.model.prefix_to_namespace(self.view.get_current(), prefix)
			else:
				(prefix, localName) = (None, name)
				namespaceURI = None
			action = ["attribute", namespaceURI, localName]
			self.view.may_record(action)
		GetArg('Select attribute:', do_attrib, ['Name:'])

	def menu_show_add_attrib(self):
		def do_it(name):
			action = ["add_attrib", "UNUSED", name]
			self.view.may_record(action)
		GetArg('Create attribute:', do_it, ['Name:'])

	def menu_show_pipe(self):
		def do_pipe(expr):
			action = ["python", expr]
			self.view.may_record(action)
		GetArg('Python expression:', do_pipe, ['Eval:'], "'x' is the old text...")

	def menu_show_xpath(self):
		def go(expr):
			action = ["xpath", expr]
			self.view.may_record(action)
		GetArg('XPath expression:', go, ['Eval:'], "Result goes on the clipboard")

	def menu_show_global(self):
		def do_global(pattern):
			action = ["do_global", pattern]
			self.view.may_record(action)
		GetArg('Global:', do_global, ['Pattern:'],
			'(@CURRENT@ is the current node\'s value)\n' +
			'Perform next action on all nodes matching')

	def menu_show_text_search(self):
		def do_text_search(pattern):
			action = ["do_text_search", pattern]
			self.view.may_record(action)
		GetArg('Search for:', do_text_search, ['Text pattern:'],
			'(@CURRENT@ is the current node\'s value)\n')

	def menu_show_search(self):
		def do_search(pattern):
			action = ["do_search", pattern]
			self.view.may_record(action)
		GetArg('Search for:',
			do_search, ['XPath:'],
			'(@CURRENT@ is the current node\'s value)')

	def menu_rename_attr(self):
		def do(name):
			action = ["rename_attrib", name]
			self.view.may_record(action)
		GetArg('Rename to:', do, ['New name:'])


	def do_create(self, action, nodeType, data):
		action = action[0]
		qname = True
		if nodeType == Node.ELEMENT_NODE:
			action += 'e'
		elif nodeType == Node.TEXT_NODE:
			action += 't'
			qname = False
		elif nodeType == Node.ATTRIBUTE_NODE:
			action += 'a'

		if qname:
			# Check name is valid
			# XXX: Should be more strict
			data = data.strip()
			assert '\n' not in data
			assert ' ' not in data

		self.view.may_record(['add_node', action, data])

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

		box = g.Dialog()
		text = g.TextView()
		box.vbox.pack_start(text, TRUE, FALSE, 0)
		text.set_size_request(400, 200)
		box.set_has_separator(False)

		box.add_button(g.STOCK_CANCEL, g.RESPONSE_CANCEL)
		box.add_button('Add _Attribute', Node.ATTRIBUTE_NODE)
		box.add_button('Add _Text', Node.TEXT_NODE)
		box.add_button('Add _Element', Node.ELEMENT_NODE)
		box.set_default_response(g.RESPONSE_OK)
		text.grab_focus()
		def response(box, resp):
			if resp == g.RESPONSE_CANCEL:
				box.destroy()
				return
			buffer = text.get_buffer()
			start = buffer.get_start_iter()
			end = buffer.get_end_iter()
			new = buffer.get_text(start, end, True)
			if new:
				self.do_create(action, resp, new)
			box.destroy()
		box.connect('response', response)

		box.show_all()
	
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
		self.parent_window.destroy()
	
	def menu_options(self):
		rox.edit_options()
	
	def menu_clear_undo(self):
		if rox.confirm('Really clear the undo buffer?',
				g.STOCK_CLEAR):
			self.view.model.clear_undo()
	
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
	do_convert_to_comment = make_do('convert_to_comment')
	do_convert_to_element = make_do('convert_to_element')
	do_convert_to_pi = make_do('convert_to_pi')
	do_remove_ns = make_do('remove_ns')

	do_clear_mark = make_do('clear_mark')
	do_mark_switch = make_do('mark_switch')
	do_mark_selection = make_do('mark_selection')
	do_select_marked = make_do('select_marked_region')
	do_select_children = make_do('select_children')

	move_home = make_do('move_home')
	move_end = make_do('move_end')
	move_left = make_do('move_left')
	move_right = make_do('move_right')
	move_next_sib = make_do('move_next_sib')
	move_prev_sib = make_do('move_prev_sib')
