from gtk import *
from GDK import *
from xml.dom.Node import Node

from Display import Display
from View import Beep
from Menu import Menu
from GetArg import GetArg
from Path import make_relative_path

class GUIView(Display):
	vmargin = 4

	def __init__(self, window, model):
		Display.__init__(self, model)
		self.window = window
		self.connect('button-press-event', self.button_event)
		self.set_events(BUTTON_PRESS_MASK)
		self.set_flags(CAN_FOCUS)
	
	def button_event(self, widget, bev):
		if bev.type != BUTTON_PRESS:
			return

		height = self.row_height
		line = int((bev.y - self.vmargin) / height)
		try:
			node = self.line_to_node[line]
		except IndexError:
			node = None
		if node and node != self.current:
			lit = bev.state & CONTROL_MASK
			ns = {}
			path = make_relative_path(self.current, node, lit, ns)
			self.may_record(["do_search", path, ns])

		if bev.button == 3:
			items = [
				('Search', self.show_search),
				#('Enter', self.chroot),
				#('Leave', self.unchroot),
				(None, None),
				#('Delete', self.delete_node),
				('Substitute', self.show_subst),
				('Process', self.show_pipe),
				(None, None),
				('Question', self.show_ask),
				(None, None),
				('Close Window', self.window.destroy),
				]
			Menu(items).popup(bev.button, bev.time)
		return 1

	def may_record(self, action):
		"Perform, and possibly record, this action"
		#rec = self.recording_where

		try:
			self.do_action(action)
		except Beep:
			gdk_beep()
			return 0

		# Only record if we were recording when this action started
		#if rec:
			#self.recording_where = rec.record(action, self.recording_exit)
			#self.recording_exit = 'next'
	
	def move_to(self, node):
		old_node = self.current
		Display.move_to(self, node)
		if old_node == self.current:
			return
		self.redraw_node(old_node)
		self.redraw_node(self.current)

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
