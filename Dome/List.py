from gtk import *
from GDK import *
from gnome.ui import *
from support import *
import string
from xml.dom.ext.reader import PyExpat
from StringIO import StringIO

import rox.choices
from rox.MultipleChoice import MultipleChoice
from Menu import Menu
from GetArg import GetArg
from Program import Program, load

def trunc(text):
	if len(text) < 18:
		return text
	return text[:16] + '...'

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
		elif action[0] == 'attribute':
			details = trunc(str(action[2]))
		elif action[0] == 'set_attrib':
			details = trunc(str(action[1]))
		elif action[0] == 'add_attrib':
			details = trunc(str(action[2]))
		elif action[0] == 'add_node':
			details = trunc(action[2])
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
		self.sub_windows = []

		self.stack_frames = GtkLabel()
		self.pack_start(self.stack_frames, FALSE, TRUE, 0)
		self.stack_frames.show()
		self.update_stack(None)

		self.tree = GtkTree()
		self.tree.unset_flags(CAN_FOCUS)
		self.chains = ChainDisplay(view, view.model.root_program)
		self.prog_tree_changed(self.view.model.root_program)

		self.pack_start(self.tree, expand = 0, fill = 1)

		swin = GtkScrolledWindow()
		swin.set_policy(POLICY_AUTOMATIC, POLICY_AUTOMATIC)
		self.pack_start(swin, expand = 1, fill = 1)
		swin.add(self.chains)
		print self.chains.size_request()
		swin.show_all()

		self.tree.show()
		self.view.lists.append(self)
		self.view.model.root_program.watchers.append(self)
		
	def set_innermost_failure(self, op):
		self.show_prog(op.program)
	
	def destroy(self):
		self.view.lists.remove(self)
		self.view.model.root_program.watchers.remove(self)
	
	def update_points(self):
		self.chains.update_points()
		for x in self.sub_windows:
			x.update_points()
	
	def program_changed(self, prog):
		pass
	
	def prog_tree_changed(self, prog = None):
		self.prog_to_tree = {}
		self.tree.clear_items(0, -1)
		self.build_tree(self.tree, self.view.model.root_program)
		# Redraw goes wrong if we don't use a callback...
		def cb(self = self, prog = prog):
			while prog:
				self.prog_to_tree[prog].expand()
				prog = prog.parent
			return 0
		idle_add(cb)
	
	def build_tree(self, tree, prog):
		item = GtkTreeItem(prog.name)
		item.connect('button-press-event', self.prog_event, prog)
		item.connect('select', lambda widget, c = self.chains, p = prog: \
							c.switch_to(p))
		item.show()
		tree.append(item)
		self.prog_to_tree[prog] = item
		if prog.subprograms:
			subtree = GtkTree()
			subtree.append(GtkTreeItem('Marker'))
			for k in prog.subprograms.values():
				self.build_tree(subtree, k)
			item.set_subtree(subtree)
	
	def run_return(self, exit):
		if exit != 'next':
			print "run_return: failure!"
			self.view.jump_to_innermost_failure()
			def cb(choice, self = self):
				if choice == 0:
					self.view.record_at_point()
			box = MultipleChoice("Program failed - record a failure case?",
					[('Record', self.view.record_at_point), 'Cancel'])
			box.set_title('Dome')
			box.show()
		print "List: execution done!"

	def prog_event(self, item, event, prog):
		if event.button == 2 or event.button == 3:
			item.emit_stop_by_name('button-press-event')
			#item.select()
			if event.button == 3:
				self.show_menu(event, prog)
			else:
				name = self.prog_to_name(prog)
				self.view.run_new(self.run_return)
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
				new = Program(name)
				prog.add_sub(new)
			GetArg('New program', create, ['Program name:'])
			
		view = self.view
		if prog.parent:
			dp = del_prog
		else:
			dp = None
		name = self.prog_to_name(prog)
		def do(play, self = self, name = name):
			def ret(play = play, self = self, name = name):
				self.view.run_new(self.run_return)
				self.view.may_record([play, name])
			return ret

		def new_view(self = self, view = view, prog = prog):
			cw = ChainWindow(view, prog)
			cw.show()
			self.sub_windows.append(cw)
			def lost_cw(win, self = self, cw = cw):
				self.sub_windows.remove(cw)
				print "closed"
			cw.connect('destroy', lost_cw)
			
		items = [
			('Play', do('play')),
			('Map', do('map')),
			('View', new_view),
			(None, None),
			('New program', new_prog),
			('Rename', rename_prog),
			('Delete', dp),
			]
		menu = Menu(items)
		menu.popup(event.button, event.time)

	def update_stack(self, op):
		"The stack has changed - redraw 'op'"
		if op and op.program == self.chains.prog:
			self.chains.update_all()
		l = len(self.view.exec_stack)
		if l == 0:
			self.stack_frames.set_text('No stack')
		elif l == 1:
			self.stack_frames.set_text('1 frame')
		else:
			self.stack_frames.set_text('%d frames' % l)
	
	def show_prog(self, prog):
		self.tree.select_child(self.prog_to_tree[prog])
	
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

		if self.view.rec_point:
			self.scroll_to_show(self.rec_point)

	def scroll_to_show(self, item):
		(lx, ly, hx, hy) = item.get_bounds()
		x, y = item.i2w(0, 0)
		x, y = self.w2c(x, y)
		lx += x
		ly += y
		hx += x
		hy += y
		lx -= 16

		sx, sy = self.get_scroll_offsets()
		if lx < sx:
			sx = lx
		if ly < sy:
			sy = ly

		(x, y, w, h) = self.get_allocation()
		hx -= w
		hy -= h
		
		if hx > sx:
			sx = hx
		if hy > sy:
			sy = hy
		
		self.scroll_to(sx, sy)
	
	def put_point(self, point):
		item = getattr(self, point)
		if item:
			item.destroy()
			setattr(self, point, None)
		
		opexit = getattr(self.view, point)
		if point == 'exec_point' and self.view.op_in_progress:
			opexit = (self.view.op_in_progress, None)
		if opexit:
			g = None
			(op, exit) = opexit
			if op.program != self.prog:
				return
			if op.program == self.prog:
				try:
					g = self.op_to_group[op]
				except KeyError:
					pass
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
			item.connect('event', self.line_event, op, exit)

			if g:
				(x1, y1) = g.i2w(0, 0)
				if exit == 'next':
					if op.next and self.op_to_group.has_key(op.next):
						(x2, y2) = self.op_to_group[op.next].i2w(0, 0)
					else:
						(x2, y2) = g.i2w(0, 20)
				elif exit == 'fail':
					if op.fail and self.op_to_group.has_key(op.fail):
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
	
	def prog_tree_changed(self, prog = None):
		pass
	
	def program_changed(self, op):
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
	
	def op_colour(self, op):
		if op in self.view.exec_stack:
			return 'cyan'
		return 'blue'
	
	def create_node(self, op, group):
		text = str(action_to_text(op.action))
		
		group.ellipse = group.add('ellipse',
					fill_color = self.op_colour(op),
					outline_color = 'black',
					x1 = -4, x2 = 4,
					y1 = -4, y2 = 4,
					width_pixels = 1)
		group.ellipse.connect('event', self.op_event, op)
		label = group.add('text',
					x = -8, 
					y = -8,
					anchor = ANCHOR_NE,
					justification = 'right',
					font = 'fixed',
					fill_color = 'black',
					text = text)

		y = 20
		if op.next:
			(lx, ly, hx, label_bottom) = label.get_bounds()
			g = group.add('group', x = 0, y = 0)
			self.create_node(op.next, g)
			(lx, ly, hx, hy) = g.get_bounds()
			drop = max(20, label_bottom + 10)
			y = drop - ly
			g.move(0, y)
			y -= 5
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
			g.move(x, y)
		group.fail_line = group.add('line',
					fill_color = '#ff6666',
					points = (6, 6, x, y),
					width_pixels = 4)
		group.fail_line.lower_to_bottom()
		group.fail_line.connect('event', self.line_event, op, 'fail')

		self.op_to_group[op] = group

		if self.view.breakpoints.has_key((op, 'next')):
			group.next_line.set(line_style = LINE_ON_OFF_DASH)
		if self.view.breakpoints.has_key((op, 'fail')):
			group.fail_line.set(line_style = LINE_ON_OFF_DASH)
	
	def edit_op(self, op):
		win = GtkWindow()
		win.set_border_width(8)
		vbox = GtkVBox(TRUE, 8)
		win.add(vbox)
		for x in op.action:
			entry = GtkEntry()
			entry.set_text(str(x))
			vbox.pack_start(entry, TRUE, FALSE, 0)
		hbox = GtkHBox(TRUE, 4)
		vbox.pack_start(hbox, TRUE, FALSE, 0)
		
		button = GtkButton("Modify")
		button.set_sensitive(FALSE)
		hbox.pack_start(button, TRUE, TRUE, 0)

		button = GtkButton("Cancel")
		hbox.pack_start(button, TRUE, TRUE, 0)
		button.connect('clicked', lambda b, win = win: win.destroy())

		win.show_all()
	
	def op_event(self, item, event, op):
		if event.type == BUTTON_PRESS:
			if event.button == 1:
				print "Clicked", op, "(in", op.program.name + ")"
				self.edit_op(op)
			else:
				self.show_op_menu(event, op)
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			item.set(fill_color = self.op_colour(op))

	def show_op_menu(self, event, op):
		del_node = None
		
		def swap_nf(self = self, op = op):
			op.swap_nf()
				
		if not (op.next and op.fail):
			def del_node(self = self, op = op):
				self.clipboard = op.del_node()
		items = [('Swap next/fail', swap_nf),
			 ('Remove node', del_node)]
		Menu(items).popup(event.button, event.time)

	def paste_chain(self, op, exit):
		print "Paste", self.clipboard
		doc = self.clipboard
		new = load(doc.documentElement)
		op.link_to(new, exit)

	def line_event(self, item, event, op, exit):
		if event.type == BUTTON_PRESS:
			if event.button == 1:
				print "Clicked exit %s of %s" % (exit, op)
				self.view.set_exec((op, exit))
			elif event.button == 2:
				self.paste_chain(op, exit)
			elif event.button == 3:
				def paste_chain(self = self, op = op, exit = exit):
					self.paste_chain(op, exit)
				def toggle_breakpoint(self = self, op = op, exit = exit):
					bp = self.view.breakpoints
					if bp.has_key((op, exit)):
						del bp[(op, exit)]
					else:
						bp[(op, exit)] = 1
					self.prog.changed()

				next = getattr(op, exit)
				if next:
					def yank_chain(self = self, op = next):
						self.clipboard = op.to_doc()
						print self.clipboard
						ext.PrettyPrint(self.clipboard)
					def del_chain(self = self, op = next):
						self.clipboard = op.del_chain()
				else:
					del_chain = None
					yank_chain = None

				items = [
					('Set/clear breakpoint', toggle_breakpoint),
					('Yank chain', yank_chain),
					('Delete chain', del_chain),
					('Paste chain', paste_chain)]
				Menu(items).popup(event.button, event.time)
		elif item != self.exec_point and item != self.rec_point:
			if event.type == ENTER_NOTIFY:
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
		#self.set_usize(max_x - min_x, -1)
	
	def canvas_to_world(self, (x, y)):
		"Canvas routine seems to be broken..."
		mx, my, maxx, maxy = self.get_scroll_region()
		sx = self.get_hadjustment().value
		sy = self.get_hadjustment().value
		return (x + mx + sx , y + my + sy)

class ChainWindow(GtkWindow):
	def __init__(self, view, prog):
		GtkWindow.__init__(self)
		swin = GtkScrolledWindow()
		self.add(swin)
		disp = ChainDisplay(view, prog)
		swin.add(disp)

		swin.show_all()
		self.disp = disp
		self.set_default_size(-1, 200)
		self.set_title(prog.name)

	def update_points(self):
		self.disp.update_points()
