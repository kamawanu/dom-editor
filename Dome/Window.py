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

		if path:
			import os.path
			path = os.path.abspath(path)
			
		import Model
		self.model = Model.Model(path)
		self.gui_view = None
		self.state = ""
		
		from GUIView import GUIView
		from List import List

		vbox = GtkVBox(FALSE, 0)
		self.add(vbox)

		toolbar = Toolbar()
		for (name, tip) in [
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

		import View
		view = View.View(self.model)
		self.view = view
		self.list = List(view)
		paned.add1(self.list)
		self.list.show()

		swin = GtkScrolledWindow()
		swin.set_policy(POLICY_AUTOMATIC, POLICY_ALWAYS)
		paned.add2(swin)

		self.gui_view = GUIView(self, view)
		swin.add(self.gui_view)
		swin.set_hadjustment(self.gui_view.get_hadjustment())
		swin.set_vadjustment(self.gui_view.get_vadjustment())

		vbox.show_all()
	
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
	
	def save(self):
		if self.savebox:
			self.savebox.destroy()
		path = self.model.uri
		self.savebox = SaveBox(self, path, 'application/x-dome')
		toggle = GtkCheckButton("Export XML")
		toggle.show()
		self.savebox.toggle_export_xml = toggle
		self.savebox.save_area.pack_start(toggle)
		self.savebox.show()
	
	def get_xml(self, export_xml = TRUE):
		print "Saving", self.view.root
		if export_xml:
			doc = self.view.model.doc
		else:
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
		export = self.savebox.toggle_export_xml
		return self.get_xml(export.get_active())
		
	def set_uri(self, uri):
		self.model.uri = uri
		self.update_title()

	# Toolbar bits

	def tool_Save(self):
		self.save()
	
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
