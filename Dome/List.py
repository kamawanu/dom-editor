from __future__ import generators

import rox
from rox import g, TRUE, FALSE, alert

from support import *
import string
from StringIO import StringIO
import math
import View

from rox.Menu import Menu

import __main__
mono = __main__.mono

prog_menu = Menu('programs', [
		('/Play', 'menu_play', '', ''),
		('/Map', 'menu_map', '', ''),
		('/View', 'menu_new_view', '', ''),
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

block_menu = Menu('op', [
	('/Toggle Enter\/Leave', 'block_toggle_enter', '', ''),
	('/Toggle Foreach','block_toggle_foreach', '', ''),
	('/Toggle Restore Mark','block_toggle_restore', '', ''),
	('/Edit comment', 'block_edit_comment', '', ''),
	('/Swap next\/fail', 'op_swap_nf', '', ''),
	('/Remove node', 'op_del_node', '', '')
])

op_menu = Menu('op', [
	('/Edit node', 'op_edit', '', ''),
	('/Swap next\/fail', 'op_swap_nf', '', ''),
	('/Remove node', 'op_del_node', '', '')
])

from GetArg import GetArg
from Program import Program, load, Block

box_size = 9
next_box = (0, 12)
fail_box = (12, 8)

def trunc(text):
	if len(text) < 28:
		return text
	return text[:26] + '...'

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
	if text == 'Start': return ''
	if text[:3] == 'do_':
		text = text[3:]
	text = string.capitalize(string.replace(text, '_', ' '))
	if text == 'Global':
		text = 'Select nodes'
	
	if len(action) > 1:
		if action[0] == 'do_search' or action[0] == 'xpath':
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
					i = string.rfind(pat[:20], ':')
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
				details = trunc(`details`)
		text = text + '\n' + details
	return text

class List(g.VBox):
	def __init__(self, view):
		g.VBox.__init__(self)

		def destroyed(widget):
			#print "List destroy!!"
			sel.disconnect(self.sel_changed_signal)
			self.view.lists.remove(self)
			self.view.model.root_program.watchers.remove(self)
		self.connect('destroy', destroyed)

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
		self.tree = tree

		cell = g.CellRendererText()
		column = g.TreeViewColumn('Program', cell, text = 0)
		tree.append_column(column)

		sel = tree.get_selection()
		# Doesn't get destroyed, so record signal number
		self.sel_changed_signal = sel.connect('changed', self.change_prog)

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
		swin.add_with_viewport(self.chains)
		swin.show_all()

		pane.set_position(200)

		sel.set_mode(g.SELECTION_BROWSE)
		root_iter = self.prog_model.get_iter_first()
		sel.select_iter(root_iter)
		tree.expand_row(self.prog_model.get_path(root_iter), FALSE)
		tree.show()
		self.view.lists.append(self)
		self.view.model.root_program.watchers.append(self)

	def change_prog(self, sel):
		selected = sel.get_selected()
		if not selected:
			return
		model, iter = selected
		if iter:
			path = model.get_value(iter, 1)
			self.chains.switch_to(self.view.name_to_prog(path))
		else:
			self.chains.switch_to(None)
		
	def set_innermost_failure(self, op):
		prog = op.get_program()
		#print "list: set_innermost_failure:", prog
		self.show_prog(prog)
	
	def update_points(self):
		self.chains.update_points()
		for x in self.sub_windows:
			x.update_points()
	
	def program_changed(self, op):
		pass
	
	def prog_tree_changed(self):
		self.prog_to_path = {}
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

		self.prog_to_path[prog] = self.prog_model.get_path(child_iter)
		for p in prog.subprograms.values():
			self.build_tree(p, child_iter)
	
	def run_return(self, exit):
		print "List execution finished:", exit
		if exit != 'next':
			#self.view.jump_to_innermost_failure()
			def record():
				if rox.confirm("Program failed - record a failure case?",
						g.STOCK_NO, 'Record'):
					self.view.record_at_point()
				return False
			g.idle_add(record)

	def button_press(self, tree, event):
		if event.button == 2 or event.button == 3:
			ret = tree.get_path_at_pos(int(event.x), int(event.y))
			if not ret:
				return 1		# Click on blank area
			path, col, cx, cy = ret
			#print "Event on", path
			iter = self.prog_model.get_iter(path)
			path = self.prog_model.get_value(iter, 1)
			if event.button == 3:
				prog = self.view.name_to_prog(path)
				self.show_menu(event, prog)
			else:
				self.view.run_new(self.run_return)
				self.view.set_status("Running '%s'" % path)
				if event.state & g.gdk.SHIFT_MASK:
					self.view.may_record(['map', path])
				else:
					self.view.may_record(['play', path])
		return 0
	
	def menu_delete(self):
		prog = self.prog_menu_prog
		if not prog.parent:
			rox.alert("Can't delete the root program!")
			return
		prog.parent.remove_sub(prog)
		
	def menu_rename(self):
		prog = self.prog_menu_prog
		def rename(name, prog = prog):
			prog.rename(name)
		GetArg('Rename program', rename, ['Program name:'])

	def menu_new_prog(self):
		prog = self.prog_menu_prog
		def create(name):
			new = Program(name)
			prog.add_sub(new)
		GetArg('New program', create, ['Program name:'])

	def menu_new_view(self):
		prog = self.prog_menu_prog
		cw = ChainWindow(self.view, prog)
		cw.show()
		self.sub_windows.append(cw)
		def lost_cw(win):
			self.sub_windows.remove(cw)
		cw.connect('destroy', lost_cw)
	
	def menu_map(self):
		prog = self.prog_menu_prog
		self.view.run_new(self.run_return)
		self.view.set_status("Running '%s'" % prog.get_path())
		self.view.may_record(['map', prog.get_path()])

	def menu_play(self):
		prog = self.prog_menu_prog
		self.view.run_new(self.run_return)
		self.view.set_status("Running '%s'" % prog.get_path())
		self.view.may_record(['play', prog.get_path()])

	def show_menu(self, event, prog):
		self.prog_menu_prog = prog
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
		path = self.prog_to_path[prog]
		partial = []
		for p in path[:-1]:
			partial.append(p)
			self.tree.expand_row(tuple(partial), FALSE)
		iter = self.prog_model.get_iter(path)
		self.tree.get_selection().select_iter(iter)

class ChainDummy(g.TreeView):
	def __init__(self, view, prog = None):
		g.TreeView.__init__(self)
		self.prog = prog
	def switch_to(self, prog):
		self.prog = prog
	def update_points(self):
		pass

class ChainNode:
	"A visual object in the display."
	def __init__(self, da, x, y):
		self.x = x
		self.y = y
		self.da = da
	
	def expose(self):
		da = self.da
		w = da.backing
		w.draw_rectangle(da.style.black_gc, True, self.x, self.y, 10, 10)

	def maybe_clicked(self, event):
		return False

class ChainOp(ChainNode):
	def __init__(self, da, op, x, y):
		self.op = op
		ChainNode.__init__(self, da, x, y)

		self.build_leaf()

		da.op_to_object[op] = self

		if op.next and op.next.prev[0] == op:
			self.next = da.create_op(op.next, x, y + self.height + 4)
		else:
			self.next = None

		if op.fail and op.fail.prev[0] == op:
			self.fail = da.create_op(op.fail, x + 100, y + self.height + 4)
		else:
			self.fail = None

	def build_leaf(self):
		text = str(action_to_text(self.op.action))
		self.layout = self.da.create_pango_layout(text)

		self.width, self.height = self.layout.get_pixel_size()
		self.width += 12
		self.height = max(self.height, 20)

	def expose(self):
		da = self.da
		w = da.backing
		op = self.op

		w.draw_arc(da.style.white_gc, True, self.x, self.y, 10, 10, 0, 400 * 60)
		w.draw_arc(da.style.black_gc, False, self.x, self.y, 10, 10, 0, 400 * 60)
		w.draw_layout(da.style.black_gc, self.x + 12, self.y, self.layout)
	
		self.draw_link(self.next, 5, 10, 'black')
		self.draw_link(self.fail, 10, 10, 'red')

		if (op, 'next') in self.da.view.breakpoints:
			w.draw_arc(da.style.black_gc, True,
					self.x + 2, self.y + 12, 6, 6, 0, 400 * 60)
		if (op, 'fail') in self.da.view.breakpoints:
			w.draw_arc(da.style.black_gc, True,
					self.x + 14, self.y + 10, 6, 6, 0, 400 * 60)

	def draw_link(self, dest, dx, dy, colour):
		if not dest: return

		dest.expose()
		da = self.da
		pen = da.style.white_gc
		pen.set_rgb_fg_color(g.gdk.color_parse(colour))
		da.backing.draw_line(pen, self.x + dx, self.y + dy, dest.x + 5, dest.y)
		pen.set_rgb_fg_color(g.gdk.color_parse('white'))
	
	def where(self, x, y):
		"Identify where (x,y) falls on us -> None, 'op', 'next', 'fail'"
		x -= self.x
		if x < 0: return False
		y -= self.y
		if y < 0: return False

		if x >= next_box[0] and y >= next_box[1] and \
		   x <= next_box[0] + box_size and y <= next_box[1] + box_size:
		   	return 'next'

		if x >= fail_box[0] and y >= fail_box[1] and \
		   x <= fail_box[0] + box_size and y <= fail_box[1] + box_size:
		   	return 'fail'

		if x < self.width and y < self.height: return 'op'
	
	def maybe_clicked(self, event):
		pos = self.where(event.x, event.y)
		if not pos: return
		if event.button == 1:
			if pos in ('next', 'fail'):
				self.da.view.set_exec((self.op, pos))
		else:
			if pos != 'op':
				self.da.show_menu(event, self.op, pos)
			else:
				self.da.show_menu(event, self.op)
		return True

	def all_nodes(self):
		yield self
		if self.next:
			for n in self.next.all_nodes(): yield n
		if self.fail:
			for n in self.fail.all_nodes(): yield n


class ChainBlock(ChainOp):
	def __init__(self, da, block, x, y):
		assert isinstance(block, Block)
		ChainOp.__init__(self, da, block, x, y)
		self.depth = 1
		p = block.parent
		while p and not isinstance(p, Program):
			p = p.parent
			self.depth += 1
	
	def build_leaf(self):
		x = self.x
		y = self.y

		if self.op.comment:
			self.layout = self.da.create_pango_layout(self.op.comment.replace('\\n', '\n'))
			self.width, height = self.layout.get_pixel_size()
			y += height + 4
		else:
			self.layout = None
			self.width = 40

		self.margin = (4 + self.op.foreach * 6, 4 + (self.op.enter + self.op.restore) * 6)
		self.width += self.margin[0]

		self.start = self.da.create_op(self.op.start, x + self.margin[0], y + self.margin[1])

		self.height = 20

		for node in self.start.all_nodes():
			self.width = max(self.width, node.x + node.width - self.x)
			self.height = max(self.height, node.y + node.height - self.y)

		self.width += 4
		self.height += 4 + (self.op.enter + self.op.restore) * 6
	
	def expose(self):
		da = self.da
		w = da.backing
		w.draw_rectangle(da.style.black_gc, False, self.x, self.y, self.width, self.height)
		pen = da.style.white_gc
		width = self.width
		x = self.x
		y = self.y

		d = 15 - min(self.depth, 7)
		pen.set_rgb_fg_color(g.gdk.color_parse('#%x%x%x' % (d, d, d)))
		w.draw_rectangle(pen, True, self.x + 1, self.y + 1, self.width - 1, self.height - 1)

		op = self.op
		if op.foreach:
			pen.set_rgb_fg_color(g.gdk.color_parse('blue'))
			w.draw_rectangle(pen, True, x + 1, y + 1, 6, self.height - 1)
			x += 6
			width -= 6

		if op.enter:
			pen.set_rgb_fg_color(g.gdk.color_parse('yellow'))
			w.draw_rectangle(pen, True, x + 1, y + 1, width - 1, 6)
			w.draw_rectangle(pen, True, x + 1, y + self.height - 6, width - 1, 6)
		if op.restore:
			pen.set_rgb_fg_color(g.gdk.color_parse('orange'))
			margin = op.enter * 6
			w.draw_rectangle(pen, True, x + 1, y + 1 + margin, width - 1, 6)
			w.draw_rectangle(pen, True, x + 1, y + self.height - 6 - margin, width - 1, 6)

		if self.layout:
			pen.set_rgb_fg_color(g.gdk.color_parse('blue'))
			w.draw_layout(pen, self.x + self.margin[0], self.y + self.margin[1], self.layout)

		pen.set_rgb_fg_color(g.gdk.color_parse('white'))

		w.draw_line(pen, self.x + 1, self.y + 1, self.x + self.width - 2, self.y + 1)
		w.draw_line(pen, self.x + 1, self.y + 1, self.x + 1, self.y + self.height - 2)
		
		self.start.expose()

		self.draw_link(self.next, 5, self.height, 'black')
		self.draw_link(self.fail, self.width, self.height, 'red')
	
	def maybe_clicked(self, event):
		return False
	
	def where(self, x, y):
		return None

class ChainDisplay(g.EventBox):
	"A graphical display of a chain of nodes."
	def __init__(self, view, prog = None):
		g.EventBox.__init__(self)
		self.connect('destroy', self.destroyed)
		self.set_app_paintable(True)
		self.set_double_buffered(False)
		self.connect('size-allocate', lambda w, a: self.size_allocate(a))

		self.view = view
		self.unset_flags(g.CAN_FOCUS)

		self.drag_last_pos = None

		self.exec_point = None		# CanvasItem, or None
		self.rec_point = None

		self.set_active(1)

		self.nodes = None
		self.subs = None
		self.set_size_request(100, 100)
	
		self.prog = None

		self.view.model.root_program.watchers.append(self)

		self.connect('expose-event', self.expose)

		self.add_events(g.gdk.BUTTON_PRESS_MASK |
				g.gdk.POINTER_MOTION_MASK)
		self.connect('button-press-event', self.button_press)
		self.hover = None
		self.connect('motion-notify-event', self.motion)

		self.switch_to(prog)
	
	def set_active(self, active):
		if mono:
			self.modify_bg(g.STATE_NORMAL, g.gdk.color_parse('white'))
		elif active:
			self.modify_bg(g.STATE_NORMAL, g.gdk.color_parse('#B3AA73'))
		else:
			self.modify_bg(g.STATE_NORMAL, g.gdk.color_parse('#FFC0C0'))
	
	def update_points(self):
		self.queue_draw()

		if self.rec_point:
			self.scroll_to_show(self.rec_point)

	def scroll_to_show(self, item):
		print "XXX"
		return

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
		if not point: return
		w = self.window
		op, exit = point
		if op.get_program() != self.prog: return
		try:
			obj = self.op_to_object[op]
		except:
			print "Can't find %s!\n" % op
			return
		x = obj.x
		y = obj.y
		size = box_size
		if point is self.view.rec_point:
			colour = 'red'
		else:
			size -= 4
			x += 2
			y += 2
			colour = 'yellow'
		if exit == 'fail':
			x += fail_box[0]
			y += fail_box[1]
		else:
			x += next_box[0]
			y += next_box[1]
		pen = self.style.white_gc
		pen.set_rgb_fg_color(g.gdk.color_parse(colour))
		w.draw_rectangle(self.style.black_gc, False, x, y, size, size)
		w.draw_rectangle(pen, True, x + 1, y + 1, size - 1, size - 1)
		pen.set_rgb_fg_color(g.gdk.color_parse('white'))
	
	def destroyed(self, widget):
		self.view.model.root_program.watchers.remove(self)
	
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
	
	def create_op(self, op, x, y):
		if isinstance(op, Block):
			return ChainBlock(self, op, x, y)
		else:
			return ChainOp(self, op, x, y)

	def update_all(self):
		self.op_to_object = {}
		if self.prog:
			self.root_object = self.create_op(self.prog.code, 4, 4)
			self.set_size_request(self.root_object.width + 8, self.root_object.height + 8)
		else:
			self.root_object = None
			self.set_size_request(-1, -1)
		self.backing = None
		self.queue_draw()
		return 1
	
	def size_allocate(self, alloc):
		self.backing = None
		self.window.clear()

	def create_backing(self):
		self.backing = g.gdk.Pixmap(self.window, self.allocation.width, self.allocation.height, -1)
		self.window.set_back_pixmap(self.backing, False)
		self.backing.draw_rectangle(self.style.bg_gc[g.STATE_NORMAL], True,
				  0, 0, self.allocation.width, self.allocation.height)
		if self.root_object:
			self.root_object.expose()
		self.window.clear()
		return
		
	def expose(self, da, event):
		if not self.backing: self.create_backing()

		self.window.draw_drawable(self.style.white_gc, self.backing, 0, 0, 0, 0, -1, -1)

		#self.update_links()
		self.put_point(self.view.rec_point)
		self.put_point(self.view.exec_point)

		#self.set_bounds()

		if self.hover:
			op, exit = self.hover
			pen = self.style.black_gc
			w = self.window
			if exit == 'fail':
				w.draw_rectangle(pen, False, op.x + fail_box[0], op.y + fail_box[1],
								box_size, box_size)
			else:
				w.draw_rectangle(pen, False, op.x + next_box[0], op.y + next_box[1],
								box_size, box_size)

	def motion(self, box, event):
		hover = None
		for op in self.op_to_object.itervalues():
			pos = op.where(event.x, event.y)
			if pos in ('next', 'fail'):
				hover = (op, pos)
		if hover == self.hover:
			return
		self.hover = hover
		self.queue_draw()
	
	def button_press(self, da, event):
		for op in self.op_to_object.itervalues():
			if op.maybe_clicked(event): break
	
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
	
	def create_node(self, op, parent):
		if op.is_toplevel():
			return obj
	
	def edit_op(self, op):
		def modify():
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
			
		win = g.Dialog()
		win.vbox.pack_start(g.Label(op.action[0]), TRUE, FALSE, 0)
		editables = []	# [ Entry | None ]
		focus = None
		for x in op.action[1:]:
			entry = g.Entry()
			entry.set_text(str(x))
			win.vbox.pack_start(entry, TRUE, FALSE, 0)
			if type(x) == str or type(x) == unicode:
				editables.append(entry)
				entry.connect('activate', lambda e: modify())
				if not focus:
					focus = entry
					entry.grab_focus()
			else:
				entry.set_editable(FALSE)
				editables.append(None)
			
		win.add_button(g.STOCK_CANCEL, g.RESPONSE_CANCEL)
		win.add_button(g.STOCK_OK, g.RESPONSE_OK)

		def response(box, resp):
			box.destroy()
			if resp == g.RESPONSE_OK:
				modify()
		win.connect('response', response)
		
		if not focus:
			win.set_response_sensitive(g.RESPONSE_OK, FALSE)

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
			item.set(fill_color = '#339900')
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
	
	def block_toggle_enter(self):
		self.op_menu_op.toggle_enter()

	def block_toggle_foreach(self):
		self.op_menu_op.toggle_foreach()

	def block_toggle_restore(self):
		self.op_menu_op.toggle_restore()

	def block_edit_comment(self):
		self.edit_comment(self.op_menu_op)

	def op_edit(self):
		self.edit_op(self.op_menu_op)

	def op_swap_nf(self):
		self.op_menu_op.swap_nf()

	def op_del_node(self):
		op = self.op_menu_op
		if op.next and op.fail:
			rox.alert("Can't delete a node with both exits in use")
			return
		self.clipboard = op.del_node()

	def show_op_menu(self, event, op):
		if op.action[0] == 'Start':
			self.op_menu_op = op.parent
			block_menu.popup(self, event)
		else:
			self.op_menu_op = op
			op_menu.popup(self, event)

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
		box = rox.Dialog()
		box.add_button(g.STOCK_CANCEL, g.RESPONSE_CANCEL)
		box.add_button(g.STOCK_ADD, g.RESPONSE_OK)
		box.set_position(g.WIN_POS_MOUSE)
		box.set_has_separator(False)

		foreach = g.CheckButton('Foreach block')
		box.vbox.pack_start(foreach)
		enter = g.CheckButton('Enter-leave block')
		box.vbox.pack_start(enter)
		box.vbox.show_all()
		
		resp = box.run()
		box.destroy()
		if resp != g.RESPONSE_OK:
			return

		b = Block(op.parent)
		if foreach.get_active():
			b.toggle_foreach()
		if enter.get_active():
			b.toggle_enter()
		op.link_to(b, exit)
		#if self.view.rec_point == (op, exit):
		self.view.single_step = 1
		if self.view.rec_point:
			self.view.stop_recording()
		self.view.set_exec((op, exit))
		try:
			self.view.do_one_step()
			assert 0
		except View.InProgress:
			pass
		print self.exec_point
		self.view.record_at_point()
		
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
		self.clipboard = next.to_doc()
		print self.clipboard
	
	def line_del_chain(self):
		op, exit = self.line_menu_line
		next = getattr(op, exit)
		if not next:
			rox.alert('Nothing to delete!')
			return
		self.clipboard = next.to_doc()
		op.unlink(exit)
	
	def show_menu(self, event, op, exit = None):
		if exit:
			self.line_menu_line = (op, exit)
			line_menu.popup(self, event)
		else:
			self.show_op_menu(event, op)

	def line_event(self, item, event, op, exit):
		# Item may be rec_point or exec_point...
		item = getattr(self.op_to_group[op], exit + '_line')

		if event.type == g.gdk.BUTTON_PRESS:
			if event.button == 1:
				if not getattr(op, exit):
					self.drag_last_pos = (event.x, event.y)
			elif event.button == 2:
				self.paste_chain(op, exit)
			elif event.button == 3:
				self.line_menu_line = (op, exit)
				line_menu.popup(self, event)
		elif event.type == g.gdk.BUTTON_RELEASE:
			if event.button == 1:
				print "Clicked exit %s of %s" % (exit, op)
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
			item.set(fill_color = '#339900')
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
