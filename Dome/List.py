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
	def __init__(self, view):
		GnomeCanvas.__init__(self)
		self.view = view
		self.unset_flags(CAN_FOCUS)

		self.exec_point = None		# CanvasItem, or None
		self.rec_point = None

		s = self.get_style().copy()
		s.bg[STATE_NORMAL] = self.get_color('light green')
		self.set_style(s)

		self.nodes = None
		self.subs = None
		self.set_usize(100, 100)

		self.view.lists.append(self)
		self.prog = None
		self.switch_to(view.model.root_program)
	
	def update_points(self):
		print "update_points"
		self.put_point('rec_point')
		self.put_point('exec_point')
	
	def put_point(self, point):
		item = getattr(self, point)
		if item:
			item.destroy()
			setattr(self, point, None)
		
		opexit = getattr(self.view, point)
		if opexit:
			(op, exit) = opexit
			if point == 'rec_point':
				c = 'red'
				s = 6
			else:
				c = 'yellow'
				s = 3
			item = self.root().add('rect',
						x1 = -s, x2 = s, y1 = -s, y2 = s,
						fill_color = c,
						outline_color = 'black', width_pixels = 1)
			setattr(self, point, item)

			if op.program == self.prog:
				g = self.op_to_group[op]
				(x1, y1) = g.i2w(0, 0)
				if exit == 'next':
					if op.next:
						(x2, y2) = self.op_to_group[op.next].i2w(0, 0)
					else:
						(x2, y2) = g.i2w(0, 20)
				elif exit == 'fail':
					if op.fail:
						(x2, y2) = self.op_to_group[op.fail].i2w(0, 0)
					else:
						(x2, y2) = g.i2w(20, 20)
				else:
					(x2, y2) = (x1, y1)
				item.move((x1 + x2) / 2, (y1 + y2) / 2)
			else:
				p = self.nearest_prog(op.program)
				g = self.prog_to_group[p]
				(x, y) = g.i2w(0, 0)
				item.move(x, y)
	
	def nearest_prog(self, prog):
		"If prog is above us, returns our parent."
		"If below us, returns the program containing it."
		"Otherwise, returns our parent."
		p = self.prog.parent
		while p:
			if p == prog:
				return self.prog.parent
			p = p.parent

		p = prog
		while p.parent:
			if p.parent == self.prog:
				return p
			p = p.parent
		return self.prog.parent
	
	def switch_to(self, prog):
		if self.prog:
			self.prog.watchers.remove(self)
		self.prog = prog
		self.prog.watchers.append(self)
		self.update_all()
	
	def program_changed(self, op):
		print "op", op, "updated"
		self.update_all()
	
	def update_all(self):
		if self.subs:
			self.subs.destroy()
		self.subs = self.root().add('group', x = 0, y = 0)

		if self.nodes:
			self.nodes.destroy()

		y = 0
		self.prog_to_group = {}
		for p in [self.prog.parent, self.prog] + self.prog.subprograms:
			if not p:
				continue
			g = self.subs.add('group', x = 0, y = y)
			self.prog_to_group[p] = g
			t = g.add('text', fill_color = 'black', x = 0, y = 0, anchor = ANCHOR_CENTER,
								text = p.name, font = 'fixed')
			(lx, ly, hx, hy) = t.get_bounds()
			if -lx > hx:
				w = -lx
			else:
				w = hx
			g.move(0, -ly)
			m = 4

			if p == self.prog:
				c = 'yellow'
			else:
				c = 'grey80'
			rect = g.add('rect', fill_color = c,
						outline_color = 'black',
						x1 = -w - m , y1 = ly - m,
						x2 = w + m , y2 = hy + m)
			t.raise_to_top()
			g.connect('event', self.subprog_event, rect, p)

			y += (hy - ly) + 12

		self.op_to_group = {}
		self.nodes = self.root().add('group', x = 0, y = y + 32)
		self.create_node(self.prog.start, self.nodes)
		self.update_points()

		self.set_bounds()
	
	def subprog_event(self, group, event, rect, sub):
		if event.type == ENTER_NOTIFY:
			rect.set(width_pixels = 2)
		elif event.type == LEAVE_NOTIFY:
			rect.set(width_pixels = 1)
		elif event.type == BUTTON_PRESS and event.button == 1:
			self.switch_to(sub)
	
	def create_node(self, op, group):
		text = action_to_text(op.action)
		
		circle = group.add('ellipse',
					fill_color = 'blue',
					outline_color = 'black',
					x1 = -4, x2 = 4,
					y1 = -4, y2 = 4,
					width_pixels = 1)
		circle.connect('event', self.op_event, op)
		label = group.add('text',
					x = -8, 
					y = 0,
					anchor = ANCHOR_EAST,
					justification = 'right',
					font = 'fixed',
					fill_color = 'black',
					text = text)

		y = 20
		if op.next:
			g = group.add('group', x = 0, y = 40)
			(lx, ly, hx, hy) = g.get_bounds()
			g.move(0, 45 - ly)
			self.create_node(op.next, g)
			y = 40
		group.next_line = group.add('line',
					fill_color = 'black',
					points = (0, 6, 0, y),
					width_pixels = 4)
		group.next_line.connect('event', self.line_event, op, 'next')

		(x, y) = (16, 16)
		if op.fail:
			y = 46
			g = group.add('group', x = 4, y = 4)
			self.create_node(op.fail, g)
			(lx, ly, hx, hy) = g.get_bounds()
			x = 20 - lx
			print "lx", lx
			g.move(x, y)
		group.fail_line = group.add('line',
					fill_color = '#ff6666',
					points = (6, 6, x, y),
					width_pixels = 4)
		group.fail_line.lower_to_bottom()
		group.fail_line.connect('event', self.line_event, op, 'fail')

		self.op_to_group[op] = group
	
	def op_event(self, item, event, op):
		if event.type == BUTTON_PRESS and event.button == 1:
			print op
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			item.set(fill_color = 'blue')

	def line_event(self, item, event, op, exit):
		if event.type == BUTTON_PRESS and event.button == 1:
			print "Clicked exit %s of %s" % (exit, op)
			self.view.set_exec((op, exit))
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			if exit == 'next':
				item.set(fill_color = 'black')
			else:
				item.set(fill_color = '#ff6666')
	
	def set_bounds(self):
		m = 8

		min_x, min_y, max_x, max_y = self.root().get_bounds()
		min_x -= m
		min_y -= m
		max_x += m
		max_y += m
		self.set_scroll_region(min_x, min_y, max_x, max_y)
		self.root().move(0, 0) # Magic!
		self.set_usize(max_x - min_x, -1)
	
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
