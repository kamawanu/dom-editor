from gtk import *
from GDK import *
from _gtk import *
import string
import os.path

from xml.dom import Node
from xml.dom import ext
from xml.dom import implementation
from xml.dom.ext.reader import PyExpat

import choices
import Html
from loader import make_xds_loader
from support import *
from SaveBox import SaveBox
from Toolbar import Toolbar

from Model import Model
from View import View
from List import List
from GUIView import GUIView

import Exec

def strip_space(doc):
	def cb(node, cb):
		if node.nodeType == Node.TEXT_NODE:
			node.data = string.strip(node.data)
			if node.data == '':
				node.parentNode.removeChild(node)
		else:
			for k in node.childNodes[:]:
				cb(k, cb)
	cb(doc.documentElement, cb)

class Window(GtkWindow):
	def __init__(self, path = None):
		GtkWindow.__init__(self)
		
		self.model = Model()
		self.gui_view = None
		
		self.set_default_size(gdk_screen_width() * 2 / 3,
				      gdk_screen_height() * 2 / 3)
		self.set_position(WIN_POS_CENTER)
		self.savebox = None

		vbox = GtkVBox(FALSE, 0)
		self.add(vbox)
		tb = Toolbar(self)
		vbox.pack_start(tb, FALSE, TRUE, 0)

		hbox = GtkHBox(FALSE, 0)
		vbox.pack_start(hbox)

		code = choices.load('Dome', 'RootProgram')
		if code:
			self.model.load_program(code)
		view = View(self.model)
		list = List(view)
		hbox.pack_start(list, FALSE, TRUE, 0)
		list.show()
		
		self.uri = "Document"

		if path:
			if path != '-':
				self.uri = path
			self.load_file(path)

		swin = GtkScrolledWindow()
		hbox.pack_start(swin, TRUE, TRUE, 0)

		Exec.exec_state = Exec.Exec(view)
		self.view = view
		self.gui_view = GUIView(self, view)
		swin.add(self.gui_view)
		swin.set_hadjustment(self.gui_view.get_hadjustment())
		swin.set_vadjustment(self.gui_view.get_vadjustment())
		swin.set_policy(POLICY_AUTOMATIC, POLICY_ALWAYS)

		vbox.show_all()
		self.connect('key-press-event', self.key)
		make_xds_loader(self, self)
	
		self.gui_view.grab_focus()
		self.update_title()
		self.connect('destroy', self.destroyed)
	
	def destroyed(self, widget):
		path = choices.save('Dome', 'RootProgram')
		if not path:
			print "Not saving macros..."
			return

		print "Saving %d macros..." % len(self.model.root_program.subprograms)
		data = self.model.root_program.to_xml()

		file = open(path, 'wb')

		file.write('<?xml version="1.0"?>\n')
		file.write(data)
		file.close()

		print "Saved to ", path


	def load_file(self, path):
		if path[-5:] == '.html':
			self.model.load_html(path)
			self.uri = path[:-5] + '.xml'
		else:
			self.model.load_xml(path)
			self.uri = path
		self.update_title()

	def load_data(self, data):
		report_error("Can only load files for now - sorry")
	
	def update_title(self):
		title = self.uri
		self.set_title(title)
	
	def key(self, widget, kev):
		if kev.keyval == F3:
			if kev.state & SHIFT_MASK:
				self.save('html')
			else:
				self.save('xml')
		return 1
	
	def save(self, type):
		if self.savebox:
			self.savebox.destroy()
		self.savebox = SaveBox(self, 'text', type)
		path = self.savebox.entry.get_chars(0, -1)
		dir, file = os.path.split(path)
		i = string.rfind(file, '.')
		if i != -1:
			file = file[:i + 1] + type
		else:
			file += '.' + type
		if dir[:1] == '/':
			dir += '/'
		else:
			dir = ''
		self.savebox.entry.set_text(dir + file)
		self.savetype = type
		self.savebox.show()
	
	def get_xml(self):
		if self.savetype == 'xml':
			doc = node_to_xml(self.gui_view.view.root)
		elif self.savetype == 'html':
			doc = node_to_html(self.gui_view.view.root)
		else:
			raise Exception('Unknown save type', self.savetype)
		self.output_data = ''
		ext.PrettyPrint(doc, stream = self)
		d = self.output_data
		self.output_data = ''
		return d
	
	def write(self, text):
		self.output_data = self.output_data + text

	def save_as(self, path):
		return send_to_file(self.get_xml(), path)

	def send_raw(self, selection_data):
		selection_data.set(selection_data.target, 8, self.get_xml())
		
	def set_uri(self, uri):
		self.uri = uri
		self.update_title()

	# Toolbar bits

	tools = [
		('Save', 'Save this macro'),
		('Record', 'Start recording a new macro'),
		('Extend', 'Record extra steps at the current point'),
		('Stop', 'Stop a running macro'),
		('Play', 'Run this macro from the start'),
		('Next', 'Run until the next step in this macro'),
		('Step', 'Run one step, stopping in any macro'),
		]
	
	def tool_Save(self):
		self.save()
	
	def tool_Stop(self):
		Exec.exec_state.stop()

	def tool_Play(self):
		Exec.exec_state.set_step_mode(-1)
		Exec.exec_state.sched()
	
	def tool_Next(self):
		Exec.exec_state.set_step_mode(1)
		Exec.exec_state.do_one_step()
	
	def tool_Step(self):
		self.view.do_one_step()
	
	def tool_Record(self):
		self.gui_view.view.toggle_record()
	
	def tool_Extend(self):
		self.gui_view.view.record_at_point()
