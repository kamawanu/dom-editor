#from __future__ import nested_scopes

import rox
from rox import g, TRUE, FALSE, alert
from gnome2 import canvas

from support import *
import string
from StringIO import StringIO
import math

from rox.Menu import Menu

prog_menu = Menu('programs', [
		('/Play', 'menu_play', '', ''),
		('/Map', 'menu_map', '', ''),
		('/View', 'menu_view', '', ''),
		('/', '', '', '<separator>'),
		('/New program', 'menu_new_prog', '', ''),
		('/Rename', 'menu_rename', '', ''),
		('/Delete', 'menu_delete', '', ''),
])

line_menu = Menu('line', [
	('/Set\/clear breakpoint', 'line_toggle_breakpoint', '', ''),
	('/Yank chain', 'line_yank_chain', '', ''),
	('/Remove link', 'line_del_chain', '', ''),
	('/Paste chain', 'line_paste_chain', '', ''),
	('/Add block', 'line_add_block', '', '')
])

#from GetArg import GetArg
from Program import Program, load, Block

no_cursor = g.gdk.Cursor(g.gdk.TCROSS)

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

expand_history = {}	# Prog name -> expanded flag

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
			while len(pat) > 20:
				i = string.rfind(pat[:20], '/')
				if i == -1:
					i = 20
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
		elif action[0] == 'subst':
			details = action[1] + ' -> ' + action[2]
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
			if len(details) > 20:
				details = `details`[:19] + '...'
		text = text + '\n' + details
	return text

class List(g.VBox):
	def __init__(self, view):
		g.VBox.__init__(self)

		self.view = view
		self.sub_windows = []

		self.stack_frames = g.Label('')
		self.pack_start(self.stack_frames, FALSE, TRUE, 0)
		self.stack_frames.show()
		self.update_stack(None)

		pane = g.VPaned()
		self.pack_start(pane, expand = 1, fill = 1)

		swin = g.ScrolledWindow()
		swin.set_policy(g.POLICY_NEVER, g.POLICY_AUTOMATIC)
		pane.add1(swin)

		self.prog_model = g.TreeStore(str, str)
		tree = g.TreeView(self.prog_model)
		tree.connect('button-press-event', self.button_press)
		tree.unset_flags(g.CAN_FOCUS)
		tree.set_headers_visible(FALSE)

		cell = g.CellRendererText()
		column = g.TreeViewColumn('Program', cell, text = 0)
		tree.append_column(column)

		sel = tree.get_selection()
		def change_prog(tree):
			selected = sel.get_selected()
			if not selected:
				return
			model, iter = selected
			path = model.get_value(iter, 1)
			self.chains.switch_to(self.view.name_to_prog(path))

		sel.connect('changed', change_prog)

		self.chains = ChainDisplay(view)
		self.prog_tree_changed()
		v = g.Viewport()
		v.add(tree)
		swin.add(v)
		v.set_shadow_type(g.SHADOW_NONE)
		v.show_all()

		swin = g.ScrolledWindow()
		swin.set_policy(g.POLICY_AUTOMATIC, g.POLICY_AUTOMATIC)
		pane.add2(swin)
		swin.add(self.chains)
		swin.show_all()

		pane.set_position(200)

		sel.set_mode(g.SELECTION_BROWSE)
		root_iter = self.prog_model.get_iter_first()
		sel.select_iter(root_iter)
		tree.expand_row(self.prog_model.get_path(root_iter), FALSE)
		tree.show()
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
		self.prog_model.clear()
		self.build_tree(self.view.model.root_program)

		# Check for now deleted programs still being displayed
		root = self.view.model.root_program
		if self.chains and self.chains.prog and not self.chains.prog.parent:
			self.chains.switch_to(None)
		for x in self.sub_windows:
			if x.disp.prog is not root and not x.disp.prog.parent:
				x.destroy()
	
	def build_tree(self, prog, iter = None):
		child_iter = self.prog_model.append(iter)
		self.prog_model.set(child_iter, 0, prog.name,
						1, prog.get_path())

		#self.prog_to_tree[prog] = item
		for p in prog.subprograms.values():
			self.build_tree(p, child_iter)
	
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

	def button_press(self, tree, event):
		if event.button == 2 or event.button == 3:
			path, col, cx, cy = tree.get_path_at_pos(event.x, event.y)
			print "Event on", path
			iter = self.prog_model.get_iter(path)
			path = self.prog_model.get_value(iter, 1)
			if event.button == 3:
				prog = self.view.name_to_prog(path)
				self.show_menu(event, prog)
			else:
				self.view.run_new(self.run_return)
				if event.state & g.gdk.SHIFT_MASK:
					self.view.may_record(['map', path])
				else:
					self.view.may_record(['play', path])
		return 0
	
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
			
		prog_menu.popup(self, event)

	def update_stack(self, op):
		"The stack has changed - redraw 'op'"
		if op and op.get_program() == self.chains.prog:
			self.chains.update_all()
		l = len(self.view.exec_stack) + len(self.view.foreach_stack)
		if l == 0:
			text = 'No stack'
		elif l == 1:
			text = '1 frame'
		else:
			text = '%d frames' % l
		if self.view.chroots:
			text += ' (%d enters)' % len(self.view.chroots)
		self.stack_frames.set_text(text)
	
	def show_prog(self, prog):
		self.tree.select_child(self.prog_to_tree[prog])

class ChainDisplay(canvas.Canvas):
	"A graphical display of a chain of nodes."
	def __init__(self, view, prog = None):
		canvas.Canvas.__init__(self)
		self.connect('destroy', self.destroyed)
		self.view = view
		self.unset_flags(g.CAN_FOCUS)

		self.drag_last_pos = None

		self.exec_point = None		# CanvasItem, or None
		self.rec_point = None

		s = self.get_style().copy()
		s.bg[g.STATE_NORMAL] = g.gdk.color_parse('light green')
		self.set_style(s)

		self.nodes = None
		self.subs = None
		self.set_size_request(100, 100)
	
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

		if not self.prog:
			return
		
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
			item = self.root().add(canvas.CanvasRect,
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
		if prog is self.prog:
			return
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
		self.nodes = self.root().add(canvas.CanvasGroup, x = 0, y = 0)
		if self.prog:
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
		if not self.prog:
			return
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
			gr = group.add(canvas.CanvasGroup, x = 0, y = 0)
			self.create_node(op.start, gr)
			#self.update_now()	# GnomeCanvas bug?
			(lx, ly, hx, hy) = gr.get_bounds()
			minx = lx - 4
			if op.foreach:
				minx -= 8
			border = gr.add(canvas.CanvasRect, x1 = minx, x2 = hx + 4, y1 = ly + 4, y2 = hy + 4,
					outline_color = 'black', width_pixels = 1)
			border.lower_to_bottom()
			if op.foreach:
				gr.add(canvas.CanvasRect, x1 = minx, x2 = minx + 8, y1 = ly + 4, y2 = hy + 4,
					fill_color = 'blue').lower_to_bottom()
			if op.enter:
				colour = 'yellow'
				gr.add(canvas.CanvasRect, x1 = minx, x2 = hx + 4, y1 = ly + 5, y2 = ly + 13,
					fill_color = colour).lower_to_bottom()
				gr.add(canvas.CanvasRect, x1 = minx, x2 = hx + 4, y1 = hy - 3, y2 = hy + 3,
					fill_color = colour).lower_to_bottom()
			if op.restore:
				colour = 'orange'
				margin = op.enter * 8
				gr.add(canvas.CanvasRect, x1 = minx, x2 = hx + 4, y1 = ly + 5 + margin, y2 = ly + 13 + margin,
					fill_color = colour).lower_to_bottom()
				gr.add(canvas.CanvasRect, x1 = minx, x2 = hx + 4, y1 = hy - 3 - margin, y2 = hy + 3 - margin,
					fill_color = colour).lower_to_bottom()
			next_off_y = 0
			group.width, group.height = hx, hy
			if op.is_toplevel():
				return
		else:
			if op.action[0] == 'Start':
				text = str(op.parent.comment.replace('\\n', '\n'))
				text_y = 0
				#text_font = '-misc-fixed-bold-r-normal-*-*-120-*-*-c-*-iso8859-1'
				text_col = 'dark blue'
			else:
				text = str(action_to_text(op.action))
				text_y = -8
				#text_font = '-misc-fixed-medium-r-normal-*-*-120-*-*-c-*-iso8859-1'
				text_col = 'black'
			
			group.ellipse = group.add(canvas.CanvasEllipse,
						fill_color = self.op_colour(op),
						outline_color = 'black',
						x1 = -4, x2 = 4,
						y1 = -4, y2 = 4,
						width_pixels = 1)
			group.ellipse.connect('event', self.op_event, op)
			if text:
				label = group.add(canvas.CanvasText,
							x = -8, 
							y = text_y,
							anchor = g.ANCHOR_NE,
							justification = 'right',
							fill_color = text_col,
							text = text)

				#self.update_now()	# GnomeCanvas bug?
				(lx, ly, hx, hy) = label.get_bounds()
				next_off_y = hy
			else:
				next_off_y = 0
			group.width, group.height = 0, 0

		if op.next and op.next.prev[0] == op:
			sx, sy = self.get_arrow_start(op, 'next')
			gr = group.add(canvas.CanvasGroup, x = 0, y = 0)
			self.create_node(op.next, gr)
			#self.update_now()	# GnomeCanvas bug?
			(lx, ly, hx, hy) = gr.get_bounds()
			drop = max(20, next_off_y + 10)
			y = drop - ly
			next = op.next
			while isinstance(next, Block):
				next = next.start
			x = next.dx
			y += next.dy
			gr.move(sx + x, sy + y)
		
		group.next_line = group.add(canvas.CanvasLine,
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
			gr = group.add(canvas.CanvasGroup, x = 0, y = 0)
			self.create_node(op.fail, gr)
			#self.update_now()	# GnomeCanvas bug?
			(lx, ly, hx, hy) = gr.get_bounds()
			x = 20 - lx
			fail = op.fail
			while isinstance(fail, Block):
				fail = fail.start
			x += fail.dx
			y += fail.dy
			gr.move(sx + x, sy + y)
		group.fail_line = group.add(canvas.CanvasLine,
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
			group.next_line.set(line_style = g.gdk.LINE_ON_OFF_DASH)
		if self.view.breakpoints.has_key((op, 'fail')):
			group.fail_line.set(line_style = g.gdk.LINE_ON_OFF_DASH)
	
	def edit_op(self, op):
		def modify(widget):
			if op.action[0] == 'do_search' or op.action[0] == 'do_global':
				t = editables[0].get_text()
				print "Checking", t
				from Ft.Xml.XPath import XPathParser
				if t.find('@CURRENT@') == -1:
					try:
						XPathParser.new().parse(t)
					except:
						alert('Invalid search pattern!')
						return
			i = 0
			for e in editables:
				i += 1
				if e:
					op.action[i] = e.get_text()
			op.changed()
			print "Done editing!"
			win.destroy()
			
		win = g.Window()
		win.set_border_width(8)
		vbox = g.VBox(TRUE, 8)
		win.add(vbox)
		vbox.pack_start(g.Label(op.action[0]), TRUE, FALSE, 0)
		editables = []	# [ Entry | None ]
		focus = None
		for x in op.action[1:]:
			entry = g.Entry()
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
			
		hbox = g.HBox(TRUE, 4)
		vbox.pack_start(hbox, TRUE, FALSE, 0)

		button = g.Button("Cancel")
		hbox.pack_start(button, TRUE, TRUE, 0)
		button.connect('clicked', lambda b, win = win: win.destroy())
		
		button = g.Button("Modify")
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
		if event.type == g.gdk.BUTTON_PRESS:
			print "Prev %s = %s" % (op, map(str, op.prev))
			if event.button == 1:
				if op.parent.start != op or not op.parent.is_toplevel():
					self.drag_last_pos = (event.x, event.y)
				else:
					self.drag_last_pos = None
			else:
				self.show_op_menu(event, op)
		elif event.type == g.gdk.BUTTON_RELEASE:
			if event.button == 1:
				self.drag_last_pos = None
				self.program_changed(None)
		elif event.type == g.gdk.ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == g.gdk.LEAVE_NOTIFY:
			item.set(fill_color = self.op_colour(op))
		elif event.type == g.gdk.MOTION_NOTIFY and self.drag_last_pos:
			if not event.state & g.gdk.BUTTON1_MASK:
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
		elif event.type == g.gdk._2BUTTON_PRESS:
			if op.action[0] == 'Start':
				self.edit_comment(op.parent)
			else:
				self.edit_op(op)
			print "(edit; stop drag!)"
			self.drag_last_pos = None
			self.program_changed(None)
		return 1

	def edit_comment(self, block):
		assert isinstance(block, Block)

		def set(comment):
			block.set_comment(comment)
		GetArg('Comment', set, ['Comment:'],
			message = '\\n for a newline', init = [block.comment])

	def show_op_menu(self, event, op):
		if op.action[0] == 'Start':
			op = op.parent
			items = [('Toggle Enter/Leave', lambda: op.toggle_enter()),
				 ('Toggle Foreach', lambda: op.toggle_foreach()),
				 ('Toggle Restore Mark', lambda: op.toggle_restore()),
				 ('Edit comment', lambda: self.edit_comment(op))]
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
			while node.action[0] == 'Start':
				node = node.parent
			src_op.link_to(node, exit)
		finally:
			self.update_all()
	
	def line_paste_chain(self):
		op, exit = self.line_menu_line
		self.paste_chain(op, exit)

	def line_add_block(self):
		op, exit = self.line_menu_line
		op.link_to(Block(op.parent), exit)
		
	def line_toggle_breakpoint(self):
		op, exit = self.line_menu_line
		bp = self.view.breakpoints
		if bp.has_key((op, exit)):
			del bp[(op, exit)]
		else:
			bp[(op, exit)] = 1
		self.prog.changed()
		
	def line_yank_chain(self):
		op, exit = self.line_menu_line
		next = getattr(op, exit)
		if not next:
			rox.alert('Nothing to yank!')
			return
		self.clipboard = op.to_doc()
		print self.clipboard
	
	def line_del_chain(self):
		op, exit = self.line_menu_line
		next = getattr(op, exit)
		if not next:
			rox.alert('Nothing to delete!')
			return
		self.clipboard = next.to_doc()
		op.unlink(exit)

	def line_event(self, item, event, op, exit):
		# Item may be rec_point or exec_point...
		item = getattr(self.op_to_group[op], exit + '_line')

		if event.type == g.gdk.BUTTON_PRESS:
			if event.button == 1:
				if not getattr(op, exit):
					self.drag_last_pos = (event.x, event.y)
					#item.grab(BUTTON_RELEASE | MOTION_NOTIFY, no_cursor, event.time)
			elif event.button == 2:
				self.paste_chain(op, exit)
			elif event.button == 3:
				self.line_menu_line = (op, exit)
				line_menu.popup(self, event)
		elif event.type == g.gdk.BUTTON_RELEASE:
			if event.button == 1:
				print "Clicked exit %s of %s" % (exit, op)
				#item.ungrab(event.time)
				self.view.set_exec((op, exit))
				self.drag_last_pos = None
				if not getattr(op, exit):
					self.end_link_drag(item, event, op, exit)
		elif event.type == g.gdk.MOTION_NOTIFY and self.drag_last_pos:
			if not event.state & g.gdk.BUTTON1_MASK:
				print "(stop drag!)"
				self.drag_last_pos = None
				if not getattr(op, exit):
					self.end_link_drag(item, event, op, exit)
				return 1
			x, y = (event.x, event.y)
			dx, dy = x - self.drag_last_pos[0], y - self.drag_last_pos[1]

			if abs(dx) > 4 or abs(dy) > 4:
				sx, sy = self.get_arrow_start(op, exit)
				x, y = item.w2i(event.x, event.y)
				gr = self.op_to_group[op]
				if exit == 'fail':
					width = gr.width
				else:
					width = 0
				item.set(points = connect(sx, sy, x, y))
		elif event.type == g.gdk.ENTER_NOTIFY:
			item.set(fill_color = 'white')
		elif event.type == g.gdk.LEAVE_NOTIFY:
			if exit == 'next':
				item.set(fill_color = 'black')
			else:
				item.set(fill_color = '#ff6666')
		return 1
	
	def get_arrow_start(self, op, exit):
		gr = self.op_to_group[op]
		return ((exit == 'fail' and gr.width) or 0, gr.height)
	
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
		#self.update_now()	# GnomeCanvas bug?
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

class ChainWindow(rox.Window):
	def __init__(self, view, prog):
		rox.Window.__init__(self)
		swin = g.ScrolledWindow()
		self.add(swin)
		disp = ChainDisplay(view, prog)
		swin.add(disp)

		swin.show_all()
		self.disp = disp
		self.set_default_size(-1, 200)
		self.set_title(prog.name)

	def update_points(self):
		self.disp.update_points()
