from gtk import *
from GDK import *
from gnome.ui import *
from support import *
import string

import choices
from Menu import Menu
from GetArg import GetArg
from Program import Program

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
	
	def new_prog(self):
		def create(name, self = self):
			new = Program(name)
			self.prog.add_sub(new)
			self.switch_to(new)
		GetArg('New program', create, ['Program name:'])
	
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
		if point == 'exec_point' and self.view.op_in_progress:
			opexit = (self.view.op_in_progress, None)
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
			if p == self.prog:
				c = 'yellow'
			else:
				c = 'grey80'
			height = self.create_prog(p.name, g, c)
			self.prog_to_group[p] = g
			g.connect('event', self.subprog_event, g.rect, p)

			y += height + 12

		self.op_to_group = {}
		self.nodes = self.root().add('group', x = 0, y = y + 32)
		self.create_node(self.prog.start, self.nodes)
		self.update_points()

		self.set_bounds()
	
	def create_prog(self, name, g, colour):
		t = g.add('text', fill_color = 'black', x = 0, y = 0, anchor = ANCHOR_CENTER,
							text = name, font = 'fixed')
		(lx, ly, hx, hy) = t.get_bounds()
		if -lx > hx:
			w = -lx
		else:
			w = hx
		g.move(0, -ly)

		m = 4
		g.rect = g.add('rect', fill_color = colour,
					outline_color = 'black',
					x1 = -w - m , y1 = ly - m,
					x2 = w + m , y2 = hy + m)
		t.raise_to_top()
		return hy - ly
	
	def subprog_event(self, group, event, rect, sub):
		if event.type == ENTER_NOTIFY:
			rect.set(width_pixels = 2)
		elif event.type == LEAVE_NOTIFY:
			rect.set(width_pixels = 1)
		elif event.type == BUTTON_PRESS:
			if event.button == 1:
				if event.state & SHIFT_MASK:
					self.view.map(sub)
				else:
					self.view.play(sub)
			elif event.button == 2:
				self.switch_to(sub)
			elif event.button == 3:
				def del_prog(self = self, sub = sub):
					parent = sub.parent
					sub.parent.remove_sub(sub)
					self.switch_to(parent)
				def rename_prog(prog = sub):
					def rename(name, prog = prog):
						prog.rename(name)
					GetArg('Rename program', rename, ['Program name:'])
				view = self.view
				if sub.parent:
					dp = del_prog
				else:
					dp = None
				items = [
					('Play', lambda view = view, s = sub: view.play(s)),
					('Map', lambda view = view, s = sub: view.map(s)),
					('View', lambda self = self, s = sub: self.switch_to(s)),
					('Rename', rename_prog),
					('Delete', dp),
					]
				menu = Menu(items)
				menu.popup(event.button, event.time)
		return 1
	
	def create_node(self, op, group):
		text = str(action_to_text(op.action))
		
		group.ellipse = group.add('ellipse',
					fill_color = 'blue',
					outline_color = 'black',
					x1 = -4, x2 = 4,
					y1 = -4, y2 = 4,
					width_pixels = 1)
		group.ellipse.connect('event', self.op_event, op)
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
		if event.type == BUTTON_PRESS:
			if event.button == 1:
				print op
			else:
				self.show_op_menu(event, op)
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			item.set(fill_color = 'blue')

	def show_op_menu(self, event, op):
		del_node = None
		del_chain = None
		
		def yank_chain(self = self, op = op):
			self.clipboard = op.to_xml()
		def swap_nf(self = self, op = op):
			op.swap_nf()
		if op.prev:
			def del_chain(self = self, op = op, yc = yank_chain):
				self.clipboard = op.del_chain()
			if not (op.next and op.fail):
				def del_node(self = self, op = op):
					self.clipboard = op.del_node()
				
		items = [('Delete chain', del_chain),
			('Yank chain', yank_chain),
			('Remove node', del_node),
			('Swap next/fail', swap_nf)]
		Menu(items).popup(event.button, event.time)

	def line_event(self, item, event, op, exit):
		if event.type == BUTTON_PRESS:
			if event.button == 1:
				print "Clicked exit %s of %s" % (exit, op)
				self.view.set_exec((op, exit))
			elif event.button == 2:
				print "Paste", self.clipboard
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			if exit == 'next':
				item.set(fill_color = 'black')
			else:
				item.set(fill_color = '#ff6666')
	
	def set_bounds(self):
		min_x, min_y, max_x, max_y = self.root().get_bounds()
		min_x -= 8
		max_x += 8
		min_y -= 8
		max_y += 8
		self.set_scroll_region(min_x, min_y, max_x, max_y)
		self.root().move(0, 0) # Magic!
		self.set_usize(max_x - min_x, -1)
	
	def canvas_to_world(self, (x, y)):
		"Canvas routine seems to be broken..."
		mx, my, maxx, maxy = self.get_scroll_region()
		sx = self.get_hadjustment().value
		sy = self.get_hadjustment().value
		print sy
		return (x + mx + sx , y + my + sy)
