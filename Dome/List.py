from gtk import *
from GDK import *
from support import *
import choices
from xml.dom.ext.reader import PyExpat

from Macro import Macro

class List(GtkVBox):
	def __init__(self, window):
		GtkVBox.__init__(self, FALSE, 0)
		self.window = window
		self.set_usize(100, -1)
		self.other_button = 0
		self.unset_flags(CAN_FOCUS)
	
	def record_new(self, i_name):
		c = 1
		name = i_name
		while 1:
			m = self.macro_named(name)
			if not m:
				break
			c += 1
			name = i_name + '_' + `c`
		
		item = GtkButton(name)
		item.set_flags(CAN_DEFAULT)
		item.unset_flags(CAN_FOCUS)
		self.pack_start(item, FALSE, FALSE, 0)
		item.show()
		macro = Macro(name, self)
		macro.connect('destroy', self.macro_died, item)
		item.set_data('macro', macro)
		item.connect('clicked', self.click)
		item.connect('button-press-event', self.press)
		item.connect('button-release-event', self.release)
		item.add_events(BUTTON_RELEASE_MASK)
		return macro
	
	def macro_died(self, macro, button):
		button.destroy()
	
	def add_from_tree(self, tree):
		# Tree is a DOM 'macro' element
		name = tree.attributes[('', 'name')].value
		print "Load", name
		new = self.record_new(str(name))
		for node in tree.childNodes:
			if node.nodeName == 'node':
				new.start.load(node)
				return
	
	def macro_named(self, name):
		"Return the Macro with this name."
		for button in self.children():
			macro = button.get_data('macro')
			if macro.uri == name:
				return macro
		return None
	
	def remove(self, macro):
		for button in self.children():
			m = button.get_data('macro')
			if m == macro:
				button.destroy()
				return
		raise Exception('Macro ' + `macro` + ' not found!')
	
	def click(self, item):
		macro = item.get_data('macro')
		item.grab_default()

		if self.button == 1:
			self.window.gui_view.playback(macro, self.shift)
		elif self.button == 2:
			macro.edit()
		else:
			macro.show_all()
	
	def press(self, button, event):
		b = event.button
		if (b == 2 or b == 3) and self.other_button == 0:
			self.other_button = b
			grab_add(button)
			button.pressed()
		return TRUE
	
	def release(self, button, event):
		self.button = event.button
		self.shift = event.state & SHIFT_MASK
		if event.button == self.other_button:
			self.other_button = 0
			grab_remove(button)
			button.released()
		return TRUE
	
	def save_all(self):
		path = choices.save('Dome', 'Macros')

		file = open(path, 'wb')
		file.write('<?xml version="1.0"?>\n<macro-list>\n')
		
		for button in self.children():
			macro = button.get_data('macro')
			file.write(macro.get_data(header = FALSE))
			file.write('\n\n')

		file.write('</macro-list>\n')
		file.close()

		print "Saved to ", path
	
	def load_all(self):
		path = choices.load('Dome', 'Macros')
		if not path:
			return

		reader = PyExpat.Reader()
		doc = reader.fromUri(path)

		for macro in doc.documentElement.childNodes:
			if macro.nodeName == 'macro':
				self.add_from_tree(macro)
	
	def child_name_changed(self, child):
		for button in self.children():
			macro = button.get_data('macro')

			if macro == child:
				button.children()[0].set_text(child.uri)
				return
