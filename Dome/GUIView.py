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
	vmargin = 4

	def __init__(self, window, view):
		Display.__init__(self, view, window.vadj)
		self.window = window
		self.connect('button-press-event', self.button_event)
		window.connect('key-press-event', self.key_press)
		self.set_events(BUTTON_PRESS_MASK)
		self.set_flags(CAN_FOCUS)
		self.recording_where = None

	def toggle_record(self, extend = FALSE):
		"Start or stop recording"
		if self.recording_where:
			self.recording_where = None
		elif extend:
			self.recording_where = Exec.exec_state.where
			if not self.recording_where:
				report_error("No current point!")
				return

			self.recording_exit = Exec.exec_state.exit
		else:
			node = self.view.current
			self.recording_where = self.view.model.macro_list.record_new(node.nodeName).start
			self.recording_exit = 'next'
		
		self.window.update_title()

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

		self.may_record(action)
		return 1
	
	def button_event(self, widget, bev):
		if bev.type != BUTTON_PRESS:
			return

		height = self.row_height
		line = int((bev.y - self.vmargin) / height)
		try:
			node = self.line_to_node[line]
		except IndexError:
			node = None
		if node and node != self.view.current:
			lit = bev.state & CONTROL_MASK
			ns = {}
			path = make_relative_path(self.view.current, node, lit, ns)
			self.may_record(["do_search", path, ns])

		if bev.button == 3:
			items = [
				('Search', self.show_search),
				('Enter', self.view.enter),
				('Leave', self.view.leave),
				(None, None),
				('Cut', lambda self = self: self.may_record(['delete_node'])),
				('Paste (replace)', lambda self = self: self.may_record(['put_replace'])),
				('Paste (inside)', lambda self = self: self.may_record(['put_as_child'])),
				('Paste (before)', lambda self = self: self.may_record(['put_before'])),
				('Paste (after)', lambda self = self: self.may_record(['put_after'])),
				(None, None),
				('Substitute', self.show_subst),
				('Process', self.show_pipe),
				(None, None),
				('Question', self.show_ask),
				(None, None),
				('Undo', lambda self = self: self.may_record(['undo'])),
				('Redo', lambda self = self: self.may_record(['redo'])),
				('Close Window', self.window.destroy),
				]
			Menu(items).popup(bev.button, bev.time)
		return 1
	
	def playback(self, macro):
		"Called when the user clicks on a macro button."
		# TODO: Reset any running macro...
		self.may_record(['playback', macro.uri])

	def may_record(self, action):
		"Perform, and possibly record, this action"
		rec = self.recording_where

		try:
			self.view.do_action(action)
		except Beep:
			gdk_beep()
			return 0

		# Only record if we were recording when this action started
		if rec:
			self.recording_where = rec.record(action, self.recording_exit)
			self.recording_exit = 'next'
			Exec.exec_state.set_pos(self.recording_where, self.recording_exit)
	
	def show_ask(self):
		def do_ask(q, self = self):
			action = ["ask", q]
			self.may_record(action)
		GetArg('Ask:', do_ask, ('Question:',))

	def show_subst(self):
		def do_subst(args, self = self):
			action = ["subst", args[0], args[1]]
			self.may_record(action)
		GetArg('Substitute:', do_subst, ('Replace:', 'With:'))

	def show_edit(self):
		edit_node(self, self.view.current)

	def show_pipe(self):
		def do_pipe(expr, self = self):
			action = ["python", expr]
			self.may_record(action)
		GetArg('Python expression:', do_pipe, ['Eval:'], "'x' is the old text...")

	def show_search(self):
		def do_search(pattern, self = self):
			action = ["do_search", pattern]
			self.may_record(action)
		GetArg('Search for:', do_search, ['Pattern:'])

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

		slash	: show_search,
		#n	: ["search_next"],

		# Interaction

		question: show_ask,

		# Changes
		I	: insert_element,
		A	: append_element,
		O	: open_element,
		
		i	: insert_text,
		a	: append_text,
		o	: open_text,

		y	: ["yank"],
		P	: ["put_before"],
		p	: ["put_after"],
		bracketright : ["put_as_child"],
		R	: ["put_replace"],

		ord('^'): ["suck"],

		Tab	: show_edit,
		exclam	: show_pipe,
		s	: show_subst,

		x	: ["delete_node"],

		# Undo/redo
		u	: ["undo"],
		r	: ["redo"],
	}
