from gtk import *
from GDK import *
from gnome.ui import *
from support import *
import string

import choices

def action_to_text(action):
	text = action[0]
	if text[:3] == 'do_':
		text = text[3:]
	text = string.capitalize(string.replace(text, '_', ' '))
	
	if len(action) > 1:
		if action[0] == 'do_search':
			pat = str(action[1])
			pat = string.replace(pat, 'following-sibling::', '>>')
			pat = string.replace(pat, 'preceding-sibling::', '<<')
			pat = string.replace(pat, 'child::', '')
			pat = string.replace(pat, '[1]', '')
			pat = string.replace(pat, 'text()[ext:match', '[')
			details = ''
			while len(pat) > 16:
				i = string.rfind(pat[:16], '/')
				if i == -1:
					i = 16
				details = details + pat[:i + 1] + '\n'
				pat = pat[i + 1:]
			details = details + pat
		elif action[0] == 'add_node':
			details = action[2]
		else:
			if len(action) > 2:
				details = `action[1:]`
			else:
				details = str(action[1])
			if len(details) > 12:
				details = `details`[:11] + '...'
		text = text + '\n' + details
	return text

class List(GnomeCanvas):
	"A graphical display of a program."
	def __init__(self, model):
		GnomeCanvas.__init__(self)
		self.model = model
		self.unset_flags(CAN_FOCUS)

		s = self.get_style().copy()
		s.bg[STATE_NORMAL] = self.get_color('light green')
		self.set_style(s)

		self.nodes = None
		self.subs = None
		self.set_usize(100, 100)

		model.root_program.watchers.append(self.update_notify)
		self.update_all()
	
	def update_notify(self, op):
		print "op", op, "updated"
		self.update_all()
	
	def update_all(self):
		if self.subs:
			self.subs.destroy()
		self.subs = self.root().add('group', x = 0, y = 0)

		if self.nodes:
			self.nodes.destroy()

		y = 0
		for p in self.model.root_program.subprograms:
			g = self.subs.add('group', x = 0, y = y)
			t = g.add('text', fill_color = 'black', x = 0, y = 0, anchor = ANCHOR_CENTER,
								text = p.name, font = 'fixed')
			(lx, ly, hx, hy) = t.get_bounds()
			print lx, ly, hx, hy
			if -lx > hx:
				w = -lx
			else:
				w = hx
			g.move(0, -ly)
			m = 4
			g.add('rect', fill_color = 'grey80', outline_color = 'black',
						x1 = -w - m , y1 = ly - m,
						x2 = w + m , y2 = hy + m)
			t.raise_to_top()

			y += (hy - ly) + 12

		self.nodes = self.root().add('group', x = 0, y = y)
		self.create_node(self.model.root_program.start, self.nodes)

		self.set_bounds()
	
	def create_node(self, op, group):
		text = action_to_text(op.action)

		next_line = group.add('line',
					fill_color = 'black',
					points = (0, 6, 0, 20),
					width_pixels = 4)
		#next_line.connect('event', self.line_event, self, 'next')

		fail_line = group.add('line',
					fill_color = '#ff6666',
					points = (6, 6, 16, 16),
					width_pixels = 4)
		#fail_line.connect('event', self.line_event, self, 'fail')
		
		circle = group.add('ellipse',
					fill_color = 'blue',
					outline_color = 'black',
					x1 = -4, x2 = 4,
					y1 = -4, y2 = 4,
					width_pixels = 1)
		label = group.add('text',
					x = -8, 
					y = 0,
					anchor = ANCHOR_EAST,
					justification = 'right',
					font = 'fixed',
					fill_color = 'black',
					text = text)
	
	def set_bounds(self):
		m = 8

		min_x, min_y, max_x, max_y = self.root().get_bounds()
		self.set_scroll_region(min_x - m, min_y - m, max_x + m, max_y + m)
		self.root().move(0, 0) # Magic!
	
class Unused:
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
