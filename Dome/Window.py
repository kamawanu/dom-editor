from gtk import *
from GDK import *
from _gtk import *
import string
import os.path
from Ft.Xml.Domlette import PrettyPrint

import __main__

from support import *
from rox.SaveBox import SaveBox
from rox.Toolbar import Toolbar

code = None

from codecs import lookup
utf8_encoder = lookup('UTF-8')[0]

class Window(GtkWindow):
	def __init__(self, path = None, data = None):
		# 'data' is used when 'path' is a stylesheet...
		GtkWindow.__init__(self)

		# Make it square, to cope with Xinerama
		size = min(gdk_screen_width(), gdk_screen_height())
		size = size * 3 / 4
		
		self.set_default_size(size, size)
		self.set_position(WIN_POS_CENTER)
		self.savebox = None

		self.show()
		gdk_flush()

		if path:
			import os.path
			path = os.path.abspath(path)
			
		import Model
		self.model = Model.Model(path, dome_data = data)
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
			('Help', "Show Dome's help file"),
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
		paned.set_position(200)

		self.gui_view = GUIView(self, view)
		swin.add(self.gui_view)
		swin.set_hadjustment(self.gui_view.get_hadjustment())
		swin.set_vadjustment(self.gui_view.get_vadjustment())

		vbox.show_all()
	
		self.gui_view.grab_focus()
		self.update_title()

		def delete(window, event):
			if self.model.root_program.modified:
				from rox.MultipleChoice import MultipleChoice
				box = MultipleChoice('Programs modified -- really quit?',
						     ('Cancel', 'Quit'))
				if box.wait() == 1:
					return 0
				return 1
			return 0
		self.connect('delete-event', delete)
		
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
		self.view.model.strip_space()
		if export_xml:
			doc = self.view.model.doc
		else:
			doc = self.view.export_all()

		from cStringIO import StringIO
		self.output_data = StringIO()
		print "Getting data..."

		PrettyPrint(doc, stream = self)
		d = self.output_data.getvalue()
		del self.output_data
		print "Got data... saving..."
		return d
	
	def write(self, text):
		if type(text) == unicode:
			text = utf8_encoder(text)[0]
		self.output_data.write(text)

	def save_get_data(self):
		export = self.savebox.toggle_export_xml
		return self.get_xml(export.get_active())
		
	def set_uri(self, uri):
		if not self.savebox.toggle_export_xml.get_active():
			self.model.uri = uri
			self.model.root_program.modified = 0
			self.update_title()

	# Toolbar bits

	def tool_Save(self):
		self.save()
	
	def tool_Stop(self):
		if self.view.rec_point:
			self.view.stop_recording()
		if self.view.running():
			self.view.single_step = 1
		else:
			self.view.run_new()

	def tool_Play(self):
		from View import InProgress, Done
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
		self.view.single_step = 2
		try:
			self.view.do_one_step()
		except InProgress, Done:
			pass
	
	def tool_Step(self):
		from View import InProgress, Done
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
	
	def tool_Help(self):
		os.spawnlp(os.P_NOWAIT, "gvim", "gvim",
			os.path.join(__main__.app_dir, "Help", "README"))
