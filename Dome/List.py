from __future__ import nested_scopes

from gtk import *
from GDK import *
import GDK
from gnome.ui import *
from support import *
import string
from xml.dom.ext.reader import PyExpat
from StringIO import StringIO
import math

import rox.choices
from rox.MultipleChoice import MultipleChoice
from Menu import Menu
from GetArg import GetArg
from Program import Program, load, Block

def trunc(text):
	if len(text) < 18:
		return text
	return text[:16] + '...'

def connect(x1, y1, x2, y2):
	"""Chop 5 pixels off both ends of this line"""
	gap = 5.0
	dx = x2 - x1
	dy = y2 - y1
	l = math.hypot(dx, dy)
	if l:
		dx *= gap / l
		dy *= gap / l
	return (x1 + dx, y1 + dy, x2 - dx, y2 - dy)

DEFAULT_NEXT = (0, 25)
DEFAULT_FAIL = (20, 20)

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
			if len(action[1]) > 20:
				details = '...' + str(action[1][-19:])
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

		pane = GtkVPaned()
		self.pack_start(pane, expand = 1, fill = 1)

		swin = GtkScrolledWindow()
		swin.set_policy(POLICY_NEVER, POLICY_AUTOMATIC)
		pane.add1(swin)

		self.tree = GtkTree()
		self.tree.unset_flags(CAN_FOCUS)

		self.chains = ChainDisplay(view, view.model.root_program)
		self.prog_tree_changed()
		v = GtkViewport()
		v.add(self.tree)
		swin.add(v)
		v.set_shadow_type(SHADOW_NONE)
		v.show_all()

		swin = GtkScrolledWindow()
		swin.set_policy(POLICY_AUTOMATIC, POLICY_AUTOMATIC)
		pane.add2(swin)
		swin.add(self.chains)
		swin.show_all()

		pane.set_position(200)

		self.tree.show()
		self.view.lists.append(self)
		self.view.model.root_program.watchers.append(self)
		
	def set_innermost_failure(self, op):
		self.show_prog(op.get_program())
	
	def destroy(self):
		self.view.lists.remove(self)
		self.view.model.root_program.watchers.remove(self)
	
	def update_points(self):
		self.chains.update_points()
		for x in self.sub_windows:
			x.update_points()
	
	def program_changed(self, op):
		pass
	
	def prog_tree_changed(self):
		self.prog_to_tree = {}
		self.tree.clear_items(0, -1)
		self.build_tree(self.tree, self.view.model.root_program)
		# Redraw goes wrong if we don't use a callback...
		def cb():
			self.prog_to_tree[self.view.model.root_program].expand()
			return 0
		idle_add(cb)

		# Check for now deleted programs still being displayed
		root = self.view.model.root_program
		if self.chains and not self.chains.prog.parent and self.chains.prog is not root:
			self.chains.switch_to(self.view.model.root_program)
		for x in self.sub_windows:
			if x.disp.prog is not root and not x.disp.prog.parent:
				x.destroy()
	
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
				name = prog.get_path()
				self.view.run_new(self.run_return)
				if event.state & SHIFT_MASK:
					self.view.may_record(['map', name])
				else:
					self.view.may_record(['play', name])
		return 1
	
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
		name = prog.get_path()
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
		if op and op.get_program() == self.chains.prog:
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
		self.connect('destroy', self.destroyed)
		self.view = view
		self.unset_flags(CAN_FOCUS)

		self.drag_last_pos = None

		self.exec_point = None		# CanvasItem, or None
		self.rec_point = None

		s = self.get_style().copy()
		s.bg[STATE_NORMAL] = self.get_color('light green')
		self.set_style(s)

		self.nodes = None
		self.subs = None
		self.set_usize(100, 100)
	
		self.prog = None

		self.view.model.root_program.watchers.append(self)

		self.switch_to(prog)
	
	def update_points(self):
		self.put_point('rec_point')
		self.put_point('exec_point')

		if self.rec_point:
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
			if op.get_program() != self.prog:
				return
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

			if g and exit:
				# TODO: cope with exit == None
				x1, y1, x2, y2 = self.get_arrow_ends(op, exit)
				x1, y1 = g.i2w(x1, y1)
				x2, y2 = g.i2w(x2, y2)
				item.move((x1 + x2) / 2, (y1 + y2) / 2)
	
	def destroyed(self, widget):
		p = self.prog
		while p.parent:
			p = p.parent
		self.view.model.root_program.watchers.remove(self)
		print "(ChainDisplay destroyed)"
	
	def switch_to(self, prog):
		self.prog = prog
		self.update_all()
	
	def prog_tree_changed(self):
		pass
	
	def program_changed(self, op):
		if (not op) or op.get_program() == self.prog:
			self.update_all()
	
	def update_all(self):
		if self.nodes:
			self.nodes.destroy()

		self.op_to_group = {}
		self.nodes = self.root().add('group', x = 0, y = 0)
		self.create_node(self.prog.code, self.nodes)
		self.update_links()
		self.update_points()

		self.set_bounds()
	
		return 1
	
	def op_colour(self, op):
		if op in self.view.exec_stack:
			return 'cyan'
		return 'blue'
	
	def update_links(self, op = None):
		"""Walk through all nodes in the tree-version of the op graph,
		making all the links (which already exist as stubs) point to
		the right place."""
		if not op:
			op = self.prog.code
		if op.next:
			if op.next.prev[0] == op:
				self.update_links(op.next)
			else:
				self.join_nodes(op, 'next')
		if op.fail:
			if op.fail.prev[0] == op:
				self.update_links(op.fail)
			else:
				self.join_nodes(op, 'fail')
		if isinstance(op, Block):
			self.update_links(op.start)
	
	def create_node(self, op, group):
		self.op_to_group[op] = group

		if isinstance(op, Block):
			g = group.add('group', x = 0, y = 0)
			self.create_node(op.start, g)
			(lx, ly, hx, hy) = g.get_bounds()
			minx = lx - 4
			if op.foreach:
				minx -= 8
			border = g.add('rect', x1 = minx, x2 = hx + 4, y1 = ly + 4, y2 = hy + 4,
					outline_color = 'black', width_pixels = 1)
			border.lower_to_bottom()
			if op.foreach:
				g.add('rect', x1 = minx, x2 = minx + 8, y1 = ly + 4, y2 = hy + 4,
					fill_color = 'blue').lower_to_bottom()
			if op.enter:
				g.add('rect', x1 = minx, x2 = hx + 4, y1 = ly + 5, y2 = ly + 13,
					fill_color = 'yellow').lower_to_bottom()
				g.add('rect', x1 = minx, x2 = hx + 4, y1 = hy - 3, y2 = hy + 3,
					fill_color = 'yellow').lower_to_bottom()
			next_off_y = 0
			group.width, group.height = hx, hy
			if op.is_toplevel():
				return
		else:
			if op.action[0] == 'Start':
				text = str(op.parent.comment.replace('\\n', '\n'))
				text_y = 0
				text_col = 'blue'
			else:
				text = str(action_to_text(op.action))
				text_y = -8
				text_col = 'black'
			
			group.ellipse = group.add('ellipse',
						fill_color = self.op_colour(op),
						outline_color = 'black',
						x1 = -4, x2 = 4,
						y1 = -4, y2 = 4,
						width_pixels = 1)
			group.ellipse.connect('event', self.op_event, op)
			if text:
				label = group.add('text',
							x = -8, 
							y = text_y,
							anchor = ANCHOR_NE,
							justification = 'right',
							font = 'fixed',
							fill_color = text_col,
							text = text)

				(lx, ly, hx, hy) = label.get_bounds()
				next_off_y = hy
			else:
				next_off_y = 0
			group.width, group.height = 0, 0

		if op.next and op.next.prev[0] == op:
			sx, sy = self.get_arrow_start(op, 'next')
			g = group.add('group', x = 0, y = 0)
			self.create_node(op.next, g)
			(lx, ly, hx, hy) = g.get_bounds()
			drop = max(20, next_off_y + 10)
			y = drop - ly
			next = op.next
			while isinstance(next, Block):
				next = next.start
			x = next.dx
			y += next.dy
			g.move(sx + x, sy + y)
		
		group.next_line = group.add('line',
					fill_color = 'black',
					points = connect(0, 0, 1, 1),
					width_pixels = 4,
					last_arrowhead = 1,
					arrow_shape_a = 5,
					arrow_shape_b = 5,
					arrow_shape_c = 5)
		group.next_line.connect('event', self.line_event, op, 'next')

		(x, y) = DEFAULT_FAIL
		if op.fail and op.fail.prev[0] == op:
			sx, sy = self.get_arrow_start(op, 'fail')
			y = 46
			g = group.add('group', x = 0, y = 0)
			self.create_node(op.fail, g)
			(lx, ly, hx, hy) = g.get_bounds()
			x = 20 - lx
			fail = op.fail
			while isinstance(fail, Block):
				fail = fail.start
			x += fail.dx
			y += fail.dy
			g.move(sx + x, sy + y)
		group.fail_line = group.add('line',
					fill_color = '#ff6666',
					points = connect(0, 0, 1, 1),
					width_pixels = 4,
					last_arrowhead = 1,
					arrow_shape_a = 5,
					arrow_shape_b = 5,
					arrow_shape_c = 5)
		group.fail_line.lower_to_bottom()
		group.fail_line.connect('event', self.line_event, op, 'fail')
		if op.action[0] == 'Start':
			group.fail_line.hide()

		self.join_nodes(op, 'next')
		self.join_nodes(op, 'fail')

		if self.view.breakpoints.has_key((op, 'next')):
			group.next_line.set(line_style = LINE_ON_OFF_DASH)
		if self.view.breakpoints.has_key((op, 'fail')):
			group.fail_line.set(line_style = LINE_ON_OFF_DASH)
	
	def edit_op(self, op):
		def modify(widget):
			i = 0
			for e in editables:
				i += 1
				if e:
					op.action[i] = e.get_text()
			op.changed()
			print "Done editing!"
			win.destroy()
			
		win = GtkWindow()
		win.set_border_width(8)
		vbox = GtkVBox(TRUE, 8)
		win.add(vbox)
		vbox.pack_start(GtkLabel(op.action[0]), TRUE, FALSE, 0)
		editables = []	# [ Entry | None ]
		focus = None
		for x in op.action[1:]:
			entry = GtkEntry()
			entry.set_text(str(x))
			vbox.pack_start(entry, TRUE, FALSE, 0)
			if type(x) == str or type(x) == unicode:
				editables.append(entry)
				entry.connect('activate', lambda e: modify(e))
				if not focus:
					focus = entry
					entry.grab_focus()
			else:
				entry.set_editable(FALSE)
				editables.append(None)
			
		hbox = GtkHBox(TRUE, 4)
		vbox.pack_start(hbox, TRUE, FALSE, 0)

		button = GtkButton("Cancel")
		hbox.pack_start(button, TRUE, TRUE, 0)
		button.connect('clicked', lambda b, win = win: win.destroy())
		
		button = GtkButton("Modify")
		if focus:
			button.connect('clicked', modify)
		else:
			button.set_sensitive(FALSE)
		hbox.pack_start(button, TRUE, TRUE, 0)

		win.show_all()
	
	def join_nodes(self, op, exit):
		try:
			x1, y1, x2, y2 = self.get_arrow_ends(op, exit)

			prev_group = self.op_to_group[op]
			line = getattr(prev_group, exit + '_line')
			line.set(points = connect(x1, y1, x2, y2))
		except Block:
			print "*** ERROR setting arc from %s:%s" % (op, exit)
	
	def op_event(self, item, event, op):
		if event.type == BUTTON_PRESS:
			print "Prev %s = %s" % (op, map(str, op.prev))
			if event.button == 1:
				if op.parent.start != op or not op.parent.is_toplevel():
					self.drag_last_pos = (event.x, event.y)
				else:
					self.drag_last_pos = None
			else:
				self.show_op_menu(event, op)
		elif event.type == BUTTON_RELEASE:
			if event.button == 1:
				self.drag_last_pos = None
				self.program_changed(None)
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			item.set(fill_color = self.op_colour(op))
		elif event.type == MOTION_NOTIFY and self.drag_last_pos:
			if not event.state & BUTTON1_MASK:
				print "(stop drag!)"
				self.drag_last_pos = None
				self.program_changed(None)
				return 1
			x, y = (event.x, event.y)
			dx, dy = x - self.drag_last_pos[0], y - self.drag_last_pos[1]
			if abs(op.dx + dx) < 4:
				dx = -op.dx
				x = dx + self.drag_last_pos[0]
			if abs(op.dy + dy) < 4:
				dy = -op.dy
				y = dy + self.drag_last_pos[1]
			op.dx += dx
			op.dy += dy
			self.drag_last_pos = (x, y)

			self.op_to_group[op].move(dx, dy)
			for p in op.prev:
				if p.next == op:
					self.join_nodes(p, 'next')
				if p.fail == op:
					self.join_nodes(p, 'fail')
			self.update_links()
			#self.create_node(self.prog.start, self.nodes)
			self.update_points()
		elif event.type == GDK._2BUTTON_PRESS:
			self.edit_op(op)
			print "(edit; stop drag!)"
			self.drag_last_pos = None
			self.program_changed(None)
		return 1

	def show_op_menu(self, event, op):
		if op.action[0] == 'Start':
			op = op.parent
			def edit_comment():
				def set(comment):
					op.set_comment(comment)
				GetArg('Comment', set, ['Comment:'],
					message = '\\n for a newline', init = [op.comment])
			items = [('Toggle Enter/Leave', lambda: op.toggle_enter()),
				 ('Toggle Foreach', lambda: op.toggle_foreach()),
				 ('Edit comment', edit_comment)]
		else:
			items = [('Edit node', lambda: self.edit_op(op))]

		del_node = None
		if not (op.next and op.fail):
			def del_node(self = self, op = op):
				self.clipboard = op.del_node()

		items += [('Swap next/fail', lambda: op.swap_nf()), ('Remove node', del_node)]
		Menu(items).popup(event.button, event.time)

	def paste_chain(self, op, exit):
		print "Paste", self.clipboard
		doc = self.clipboard
		new = load(doc.documentElement, op.parent)
		start = new.start.next
		new.start.unlink('next', may_delete = 0)
		start.set_parent(None)
		op.link_to(start, exit)
	
	def end_link_drag(self, item, event, src_op, exit):
		# Scan all the nodes looking for one nearby...
		x, y = event.x, event.y

		def closest_node(op):
			"Return the closest (node, dist) in this chain to (x, y)"
			nx, ny = self.op_to_group[op].i2w(0, 0)
			if op is src_op:
				best = None
			elif isinstance(op, Block):
				best = None
			else:
				best = (op, math.hypot(nx - x, ny - y))
			if op.next and op.next.prev[0] == op:
				next = closest_node(op.next)
				if next and (best is None or next[1] < best[1]):
					best = next
			if op.fail and op.fail.prev[0] == op:
				fail = closest_node(op.fail)
				if fail and (best is None or fail[1] < best[1]):
					best = fail
			if isinstance(op, Block):
				sub = closest_node(op.start)
				if sub and (best is None or sub[1] < best[1]):
					best = sub
			return best
		
		result = closest_node(self.prog.code)
		if result:
			node, dist = result
		else:
			dist = 1000
		if dist > 12:
			# Too far... put the line back to the disconnected state...
			self.join_nodes(src_op, exit)
			return
		try:
			src_op.link_to(node, exit)
		finally:
			self.update_all()

	def line_event(self, item, event, op, exit):
		# Item may be rec_point or exec_point...
		item = getattr(self.op_to_group[op], exit + '_line')

		if event.type == BUTTON_PRESS:
			if event.button == 1:
				if not getattr(op, exit):
					self.drag_last_pos = (event.x, event.y)
			elif event.button == 2:
				self.paste_chain(op, exit)
			elif event.button == 3:
				def paste_chain():
					self.paste_chain(op, exit)
				def add_block():
					op.link_to(Block(op.parent), exit)
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
					def del_chain():
						self.clipboard = next.to_doc()
						op.unlink(exit)
				else:
					del_chain = None
					yank_chain = None

				items = [
					('Set/clear breakpoint', toggle_breakpoint),
					('Yank chain', yank_chain),
					('Remove link', del_chain),
					('Paste chain', paste_chain),
					('Add block', add_block)]
				Menu(items).popup(event.button, event.time)
		elif event.type == BUTTON_RELEASE:
			if event.button == 1:
				print "Clicked exit %s of %s" % (exit, op)
				self.view.set_exec((op, exit))
				self.drag_last_pos = None
				if not getattr(op, exit):
					self.end_link_drag(item, event, op, exit)
		elif event.type == MOTION_NOTIFY and self.drag_last_pos:
			x, y = (event.x, event.y)
			dx, dy = x - self.drag_last_pos[0], y - self.drag_last_pos[1]

			if abs(dx) > 4 or abs(dy) > 4:
				sx, sy = self.get_arrow_start(op, exit)
				x, y = item.w2i(event.x, event.y)
				g = self.op_to_group[op]
				if exit == 'fail':
					width = g.width
				else:
					width = 0
				item.set(points = connect(sx, sy, x, y))
		elif event.type == ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == LEAVE_NOTIFY:
			if exit == 'next':
				item.set(fill_color = 'black')
			else:
				item.set(fill_color = '#ff6666')
		return 1
	
	def get_arrow_start(self, op, exit):
		g = self.op_to_group[op]
		return ((exit == 'fail' and g.width) or 0, g.height)
	
	def get_arrow_ends(self, op, exit):
		"""Return coords of arrow, relative to op's group."""
		op2 = getattr(op, exit)

		prev_group = self.op_to_group[op]

		x1, y1 = self.get_arrow_start(op, exit)

		if op2:
			try:
				group = self.op_to_group[op2]
			except:
				x2 = x1 + 50
				y2 = y1 + 50
			else:
				x2, y2 = group.i2w(0, 0)
				x2, y2 = prev_group.w2i(x2, y2)
		elif exit == 'next':
			x2, y2 = DEFAULT_NEXT
			x2 += x1
			y2 += y1
		else:
			x2, y2 = DEFAULT_FAIL
			x2 += x1
			y2 += y1
		return (x1, y1, x2, y2)
	
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
