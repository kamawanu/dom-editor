from gtk import *
from GDK import *
from _gtk import *
import string
import os.path

import __main__

from support import *
from rox.SaveBox import SaveBox
from rox.Toolbar import Toolbar

code = None

class Window(GtkWindow):
	def __init__(self, path = None):
		GtkWindow.__init__(self)
		
		self.set_default_size(gdk_screen_width() * 2 / 3,
				      gdk_screen_height() * 2 / 3)
		self.set_position(WIN_POS_CENTER)
		self.savebox = None

		self.show()
		gdk_flush()

		import Model
		self.model = Model.Model('Document')
		self.gui_view = None
		self.state = ""
		
		from Program import Program, load_dome_program
		from GUIView import GUIView
		from List import List

		vbox = GtkVBox(FALSE, 0)
		self.add(vbox)

		toolbar = Toolbar()
		for (name, tip) in [
			('SaveAll', 'Save both program and document'),
			('Save', 'Save this document'),
			('Record', 'Start recording here'),
			('Stop', 'Stop recording or running program'),
			('Play', 'Run this program from here'),
			('Next', 'Run until the next step in this program'),
			('Step', 'Run one step, stopping in any program'),
			]:
			icon = __main__.app_dir + '/icons/%s.xpm' % name
			b = toolbar.add_button(name, icon, tip)
			cb = getattr(self, 'tool_%s' % name)
			b.connect('clicked', lambda b, cb = cb: cb())

		vbox.pack_start(toolbar, FALSE, TRUE, 0)

		paned = GtkHPaned()
		vbox.pack_start(paned)

		root_program = None
		data_to_load = None

		if path:
			if path != '-':
				self.model.uri = path
			from xml.dom.ext.reader import PyExpat
			reader = PyExpat.Reader()
			doc = reader.fromUri(path)
			root = doc.documentElement
			import constants
			if root.namespaceURI == constants.DOME_NS and root.localName == 'dome':
				for x in root.childNodes:
					if x.namespaceURI == constants.DOME_NS:
						if x.localName == 'dome-program':
							root_program = load_dome_program(x)
						elif x.localName == 'dome-data':
							for y in x.childNodes:
								if y.nodeType == Node.ELEMENT_NODE:
									data_to_load = y
			else:
				data_to_load = root

		if not root_program:
			root_program = Program('Root')

		import View
		view = View.View(self.model, root_program)
		self.view = view
		self.list = List(view)
		paned.add1(self.list)
		self.list.show()

		if data_to_load:
			self.view.load_node(data_to_load)
		
		swin = GtkScrolledWindow()
		swin.set_policy(POLICY_AUTOMATIC, POLICY_ALWAYS)
		paned.add2(swin)

		self.gui_view = GUIView(self, view)
		swin.add(self.gui_view)
		swin.set_hadjustment(self.gui_view.get_hadjustment())
		swin.set_vadjustment(self.gui_view.get_vadjustment())

		vbox.show_all()
		self.connect('key-press-event', self.key)
	
		self.gui_view.grab_focus()
		self.update_title()
		
	def set_state(self, state):
		if state == self.state:
			return
		if state:
			self.state = " " + state
		else:
			self.state = ""

		self.update_title()

	def update_title(self):
		title = self.model.uri
		self.set_title(title + self.state)
	
	def key(self, widget, kev):
		if kev.keyval == F3:
			self.save()
		return 1
	
	def save(self):
		if self.savebox:
			self.savebox.destroy()
		path = self.model.uri
		self.savebox = SaveBox(self, path, 'application/x-dome')
		self.savebox.show()
	
	def get_xml(self):
		print "Saving", self.view.root
		doc = self.view.export_all()
		self.output_data = ''
		from xml.dom import ext
		ext.PrettyPrint(doc, stream = self)
		d = self.output_data
		self.output_data = ''
		return d
	
	def write(self, text):
		self.output_data = self.output_data + text

	def save_get_data(self):
		return self.get_xml()
		
	def set_uri(self, uri):
		self.model.uri = uri
		self.update_title()

	# Toolbar bits

	def tool_SaveAll(self):
		self.save('dome')
	
	def tool_Save(self):
		self.save('xml')
	
	def tool_Stop(self):
		if self.view.rec_point:
			self.view.stop_recording()
		self.view.run_new()

	def tool_Play(self):
		from View import InProgress, Done
		if not self.view.callback_on_return:
			self.view.run_new(self.list.run_return)
		else:
			print "Continue with current stack frame"
		# Step first, in case we're on a breakpoint
		self.view.single_step = 1
		try:
			self.view.do_one_step()
		except InProgress, Done:
			pass
		self.view.single_step = 0
		self.view.sched()
	
	def tool_Next(self):
		from View import InProgress, Done
		if not self.view.callback_on_return:
			self.view.run_new(self.list.run_return)
		self.view.single_step = 2
		try:
			self.view.do_one_step()
		except InProgress, Done:
			pass
	
	def tool_Step(self):
		from View import InProgress, Done
		if not self.view.callback_on_return:
			self.view.run_new(self.list.run_return)
		self.view.single_step = 1
		try:
			self.view.do_one_step()
		except InProgress, Done:
			pass
	
	def tool_Record(self):
		if self.view.rec_point:
			self.view.stop_recording()
		else:
			self.view.record_at_point()
