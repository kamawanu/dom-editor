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
		elif action[0] == 'play' or action[0] == 'map':
			if len(action[1]) > 10:
				details = '...' + str(action[1][-9:])
			else:
				details = str(action[1])
		else:
			if len(action) > 2:
				details = `action[1:]`
			else:
				details = str(action[1])
			if len(details) > 12:
				details = `details`[:11] + '...'
		text = text + '\n' + details
	return text

class List(GtkVBox):
	def __init__(self, view):
		GtkVBox.__init__(self)

		self.view = view

		self.tree = GtkTree()
		self.tree.unset_flags(CAN_FOCUS)
		self.chains = ChainDisplay(view, view.model.root_program)

		self.pack_start(self.tree, expand = 0, fill = 1)

		hbox = GtkHBox()
		self.pack_start(hbox, expand = 1, fill = 1)
		hbox.pack_start(self.chains, 1, 1)
		sb = GtkVScrollbar(self.chains.get_vadjustment())
		hbox.pack_start(sb, 0, 1)
		self.chains.connect('size-allocate', self.chain_resize, sb)

		self.build_tree(self.tree, view.model.root_program)
		self.chains.show()
		self.tree.show()
		for i in self.tree.children():
			i.expand()
		self.view.lists.append(self)
	
	def update_points(self):
		self.chains.update_points()
	
	def prog_tree_changed(self):
		self.tree.clear_items(0, -1)
		self.build_tree(self.tree, self.view.model.root_program)
	
	def chain_resize(self, canvas, c, sb):
		adj = canvas.get_vadjustment()
		if adj.upper - adj.lower > adj.page_size:
			sb.show()
		else:
			sb.hide()

	def build_tree(self, tree, prog):
		item = GtkTreeItem(prog.name)
		item.connect('button-press-event', self.prog_event, prog)
		item.connect('select', lambda widget, c = self.chains, p = prog: \
							c.switch_to(p))
		item.show()
		tree.append(item)
		if prog.subprograms:
			subtree = GtkTree()
			subtree.append(GtkTreeItem('Marker'))
			for k in prog.subprograms.values():
				self.build_tree(subtree, k)
			item.set_subtree(subtree)

	def prog_event(self, item, event, prog):
		if event.button == 2 or event.button == 3:
			item.emit_stop_by_name('button-press-event')
			#item.select()
			if event.button == 3:
				self.show_menu(event, prog)
			else:
				name = self.prog_to_name(prog)
				self.view.single_step = 0
				if event.state & SHIFT_MASK:
					self.view.may_record(['map', name])
				else:
					self.view.may_record(['play', name])
		return 1
	
	def prog_to_name(self, prog):
		path = ""
		p = prog
		while p:
			path = p.name + '/' + path
			p = p.parent
		return path[:-1]

	def show_menu(self, event, prog):
		def del_prog(self = self, prog = prog):
			parent = prog.parent
			prog.parent.remove_sub(prog)
		def rename_prog(prog = prog):
			def rename(name, prog = prog):
				prog.rename(name)
			GetArg('Rename program', rename, ['Program name:'])
		def new_prog(model = self.view.model, prog = prog):
			def create(name, model = model, prog = prog):
				new = Program(model, name)
				prog.add_sub(new)
			GetArg('New program', create, ['Program name:'])
			
		view = self.view
		if prog.parent:
			dp = del_prog
		else:
			dp = None
		name = self.prog_to_name(prog)
		def do(play, view = view, name = name):
			def ret(play = play, view = view, name = name):
				view.single_step = 0
				view.may_record([play, name])
			return ret
		items = [
			('Play', do('play')),
			('Map', do('map')),
			(None, None),
			('New program', new_prog),
			('Rename', rename_prog),
			('Delete', dp),
			]
		menu = Menu(items)
		menu.popup(event.button, event.time)
	
class ChainDisplay(GnomeCanvas):
	"A graphical display of a chain of nodes."
	def __init__(self, view, prog):
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
	
		self.prog = None
		self.switch_to(prog)
	
	def update_points(self):
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
			if op.program != self.prog:
				return
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
		if self.nodes:
			self.nodes.destroy()

		self.op_to_group = {}
		self.nodes = self.root().add('group', x = 0, y = 0)
		self.create_node(self.prog.start, self.nodes)
		self.update_points()

		self.set_bounds()
	
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
