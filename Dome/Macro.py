from gtk import *
from GDK import *
from gnome.ui import *
import __main__
from loader import make_xds_loader
from xml.parsers.xmlproc.utils import escape_attval
from xml.dom.ext.reader import PyExpat
from StringIO import StringIO
import string

from support import *

import Exec
from SaveBox import SaveBox
from Menu import Menu

clipboard = None

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

class Macro(GtkWindow):
	def __init__(self, uri, parent):
		GtkWindow.__init__(self)
		self.uri = uri
		self.update_title()
		self.parent = parent
		self.set_position(WIN_POS_MOUSE)

		self.vbox = GtkVBox(FALSE, 0)
		self.add(self.vbox)
		
		canvas = GnomeCanvas()
		view = GtkScrolledWindow(canvas.get_hadjustment(),
					 canvas.get_vadjustment())
		view.set_policy(POLICY_ALWAYS, POLICY_AUTOMATIC)
		self.vbox.pack_end(view)
		view.add(canvas)

		self.canvas = canvas
		s = canvas.get_style().copy()
		s.bg[STATE_NORMAL] = canvas.get_color('light green')
		canvas.set_style(s)
		
		self.root = canvas.root()

		self.start = MacroNode(self, ['Start'])

		def del_cb(self, win):
			self.hide()
			return 1
		self.connect('delete_event', del_cb)

		self.savebox = None
		self.connect('key-press-event', self.key)

		make_xds_loader(self, self)
		width = self.set_bounds()

		self.is_destroyed = 0
		self.connect('destroy', self.destroyed)
	
	def destroyed(self, widget):
		self.is_destroyed = 1
	
	def edit(self):
		"Box for editing the name / removing the macro"
		if self.is_destroyed:
			return

		win = GtkWindow(WINDOW_DIALOG)
		win.set_border_width(10)

		vbox = GtkVBox(FALSE, 4)
		win.add(vbox)

		hbox = GtkHBox(FALSE, 4)
		vbox.pack_start(hbox, TRUE, TRUE, 0)

		hbox.pack_start(GtkLabel('Name'), FALSE, TRUE, 0)
		entry = GtkEntry()
		entry.connect('activate', self.edit_button, 0, win, entry)
		hbox.pack_start(entry, TRUE, TRUE, 0)
		entry.grab_focus()
		entry.set_text(self.uri)
		entry.select_region(0, -1)

		vbox.pack_start(GtkHSeparator(), TRUE, TRUE, 8)

		hbox = GtkHBox(TRUE, 4)
		vbox.pack_start(hbox, FALSE, TRUE, 0)

		button = GtkButton('OK')
		button.set_flags(CAN_DEFAULT)
		hbox.pack_start(button, FALSE, TRUE, 0)
		button.grab_default()
		button.connect('clicked', self.edit_button, 0, win, entry)
		
		button = GtkButton('Delete')
		button.set_flags(CAN_DEFAULT)
		hbox.pack_start(button, FALSE, TRUE, 0)
		button.connect('clicked', self.edit_button, 1, win)
		
		button = GtkButton('Cancel')
		button.set_flags(CAN_DEFAULT)
		hbox.pack_start(button, FALSE, TRUE, 0)
		button.connect('clicked', self.edit_button, 2, win)
		
		win.show_all()
	
	def edit_button(self, button, code, win, entry = None):
		if not self.is_destroyed:
			if code == 0:
				self.set_uri(entry.get_chars(0, -1))
			elif code == 1:
				self.destroy()
		win.destroy()
	
	def load_file(self, file):
		f = open(file, 'r')
		data = f.read()
		f.close()
		self.load_data(data)

	def load_data(self, data):
		reader = PyExpat.Reader()
		doc = reader.fromStream(StringIO(data))
		self.start.load(doc.documentElement)
	
	def update_title(self):
		self.set_title(self.uri)

	def key(self, canvas, kev):
		key = kev.keyval

		if key == F3:
			self.save()
	
	def save(self):
		if self.savebox:
			self.savebox.destroy()
		self.savebox = SaveBox(self, 'text', 'xml')
		self.savebox.show_all()
	
	def get_data(self, header = 1):
		if header:
			data = '<?xml version="1.0"?>\n'
		else:
			data = ''

		data += '<macro name="%s">\n' % escape_attval(self.uri)

		data = data + self.start.add()
		return data + '</macro>'
	
	def save_as(self, path):
		return send_to_file(self.get_data(), path)

	def send_raw(self, selection_data):
		selection_data.set(selection_data.target, 8, self.get_data())
	
	def set_uri(self, uri):
		self.uri = uri
		self.update_title()
		self.parent.child_name_changed(self)
	
	def set_bounds(self):
		"Sets the default size if not yet open"
		min_x, min_y, max_x, max_y = self.root.get_bounds()
		m = 8
		self.canvas.set_scroll_region(min_x - m, min_y - m, max_x + m, max_y + m)
		self.root.move(0, 0) # Magic!

		width = max_x - min_x + 50
		height = max_y - min_y + 50
		max_w = screen_width() * 2 / 3
		max_h = screen_height() * 2 / 3
		if width > max_w:
			width = max_w
		if height > max_h:
			height = max_h
		if not self.flags(REALIZED):
			self.set_default_size(width, height)

class MacroNode:
	def __init__(self, parent, action, x = 50, y = 50, p_node = None):
		self.macro = parent
		self.action = action
		self.next = None
		self.fail = None

		text = action_to_text(action)
		
		if p_node:
			p_group = p_node.group
			self.prev = p_node
		else:
			p_group = parent.root
			self.prev = None

		self.group = p_group.add('group', x = x, y = y)
		
		self.next_line = self.group.add('line',
					fill_color = 'black',
					points = (0, 6, 0, 20),
					width_pixels = 4)
		self.next_line.connect('event', self.line_event, self, 'next')

		self.fail_line = self.group.add('line',
					fill_color = '#ff6666',
					points = (6, 6, 16, 16),
					width_pixels = 4)
		self.fail_line.connect('event', self.line_event, self, 'fail')
		
		self.circle = self.group.add('ellipse',
					fill_color = 'blue',
					outline_color = 'black',
					x1 = -4, x2 = 4,
					y1 = -4, y2 = 4,
					width_pixels = 1)
		self.label = self.group.add('text',
					x = -8, 
					y = 0,
					anchor = ANCHOR_EAST,
					justification = 'right',
					font = 'fixed',
					fill_color = 'black',
					text = text)
		self.group.connect('event', self.event)
		self.marker = None
	
	def reparent(self, new_parent, exit = 'next'):
		self.prev = new_parent
		self.group.reparent(new_parent.group)
		new_parent.link_to(self, exit)
	
	def highlight(self, colour):
		self.circle.set(fill_color = colour)
	
	def link_to(self, child, exit):
		# Create a line from this exit to this child
		setattr(self, exit, child)
		self.child_moved(child)
	
	def forget_child(self, child):
		if child.prev != self:
			raise Exception('forget_child: not my child!')
		child.prev = None

		if child == self.next:
			exit = 'next'
			points = (0, 6, 0, 20)
		else:
			exit = 'fail'
			points = (6, 6, 16, 16)
		setattr(self, exit, None)
		getattr(self, '%s_line' % exit).set(points = points)

		exec_state = self.get_exec_state()
		exec_state.set_pos(None)
		self.macro.set_bounds()
	
	def get_exec_state(self):
		# This is a bit dodgy, since there could be several states
		# using a single macro in the future...
		return Exec.exec_state
				
	def kill_child(self, child):
		child.group.destroy()

		self.forget_child(child)
	
	def add_child(self, action, exit):
		new = MacroNode(self.macro, action, x = 0, y = 0, p_node = self)

		old = getattr(self, exit)
	
		if exit == 'next':
			dx = 0
			dy = 60
		else:
			dx = 120
			dy = 40

		new.group.move(dx, dy)

		if old:
			old.reparent(new)

		setattr(self, exit, new)

		self.link_to(new, exit)

		self.macro.set_bounds()

		return new
	
	def paste_clipboard(self, exit):
		print "Paste %s:%s:\n%s" % (self, exit, clipboard)
		if not clipboard:
			raise Exception('No clipboard!')

		reader = PyExpat.Reader()
		doc = reader.fromStream(StringIO(clipboard))
		self.load(doc.documentElement, exit = exit)
	
	def line_event(self, line, event, prev, exit):
		if event.type == BUTTON_PRESS:
			if event.button == 1:
				self.get_exec_state().set_pos(prev, exit, 0.5)
			elif event.button == 2:
				prev.paste_clipboard(exit)
		return 1
	
	def show_menu(self, event):
		if self.next and self.fail:
			del_node = None
		else:
			del_node = self.del_node
		del_chain = self.del_chain

		if not self.prev:
			del_node = None
			del_chain = None

		items = [('Delete chain', del_chain),
			('Remove node', del_node),
			('Swap next/fail', self.swap_nf)]
		Menu(items).popup(event.button, event.time)

	def swap_nf(self):
		next = self.next
		fail = self.fail
		if next:
			self.forget_child(next)
		if fail:
			self.forget_child(fail)
		if next:
			next.reparent(self, 'fail')
		if fail:
			fail.reparent(self, 'next')
	
	def del_node(self):
		prev = self.prev
		if prev.next == self:
			exit = 'next'
		else:
			exit = 'fail'
		prev.forget_child(self)
		if self.next:
			self.next.reparent(prev, exit)
			self.next = None
		elif self.fail:
			self.fail.reparent(prev, exit)
			self.fail = None
		global clipboard
		clipboard = self.add()
		self.group.destroy()
		#self.prev.kill_child(self)
	
	def del_chain(self):
		global clipboard
		clipboard = self.add()
		self.prev.kill_child(self)
	
	def event(self, group, event):
		if event.type == BUTTON_PRESS:
			if event.button == 1:
				exec_state = self.get_exec_state()
				exec_state.clean()
				if self.prev:
					if self.prev.next == self:
						exec_state.set_pos(self.prev, 'next')
					else:
						exec_state.set_pos(self.prev, 'fail')
				else:
					exec_state.set_pos(self, 'next', how_far = 0.1)
			elif event.button == 3:
				self.show_menu(event)
				return 1
					
			self.drag_last_x = event.x
			self.drag_last_y = event.y
		elif event.type == MOTION_NOTIFY:
			if event.state & GDK.BUTTON2_MASK:
				dx = event.x - self.drag_last_x
				dy = event.y - self.drag_last_y
				# XXX pixel diffs
				group.move(dx, dy)
				self.drag_last_x = event.x
				self.drag_last_y = event.y
				if self.prev:
					self.prev.child_moved(self)
		elif event.type == BUTTON_RELEASE:
			self.macro.set_bounds()
		return 1
	
	def child_pos(self, child):
		(x, y) = child.group.i2w(0, 0)
		return self.group.w2i(x, y)
	
	def child_moved(self, child):
		# Adjust the link endpoint...
		if child == self.next:
			line = self.next_line
		else:
			line = self.fail_line
		(x1, y1) = (0, 6)
		(x2, y2) = child.group.i2w(0, -6)
		(x2, y2) = self.group.w2i(x2, y2)
		line.set(points = (x1, y1, x2, y2))

		if self.marker:
			self.set_exec_point(self.where, self.how_far)
	
	def add(self):
		next = self.next
		fail = self.fail
		act = escape_attval(`self.action`)
		ret = '<node action="%s"' % act
		if next == None and fail == None:
			return ret + '/>\n'
		ret += '>\n'

		if fail:
			ret += '<fail>\n' + fail.add() + '</fail>'

		if next:
			return ret + next.add() + '</node>'
		return ret + '</node>'

	def set_exec_point(self, where, how_far = 0.9):
		"'where' is 'next', 'fail' or None (to remove the marker)"
		"how_far is the fraction of the way along the line to put the marker"

		if self.marker:
			self.marker.destroy()
			self.marker = None
		self.how_far = how_far
		if where:
			if where == 'next':
				colour = 'yellow'
			elif where == 'fail':
				colour = 'red'
			else:
				raise Exception("Bad position for set_exec_point()")

			self.marker = self.group.add('ellipse',
						fill_color = colour,
						outline_color = 'black',
						x1 = -4, x2 = 4,
						y1 = -4, y2 = 4,
						width_pixels = 1)

			if where == 'next':
				dx, dy = (0, 6)
			else:
				dx, dy = (6, 6)

			node = getattr(self, where)
			if node:
				ndx, ndy = self.child_pos(node)
				dx += (ndx - dx) * how_far
				dy += (ndy - dy) * how_far

			self.marker.move(dx, dy)
			self.where = where
	
	def record(self, action, exit = 'next'):
		if self.macro.is_destroyed:
			raise Exception('Macro no longer exists!')
		return self.add_child(action, exit)
	
	def __str__(self):
		return "{" + `self.action` + "}"

	# Data is <node action="...">[<fail>][<node>]</node> for the CURRENT node
	# unless 'exit' is given, in which case the node is added to that exit.
	def load(self, node, exit = None):
		def action(node):
			attr = node.attributes[('', 'action')]
			action = eval(str(attr.value))
			if action[0] == 'chroot':
				action[0] = 'enter'
			elif action[0] == 'unchroot':
				action[0] = 'leave'
			elif action[0] == 'playback':
				action[0] = 'map'
			return action
			
		if exit:
			new = self.record(action(node), exit)
			new.load(node)
			return

		next = None
		fail = None
		for k in node.childNodes:
			if k.nodeName == 'node':
				next = k
			elif k.nodeName == 'fail':
				fail = k
				
		if next:
			self.record(action(next), 'next')
			self.next.load(next)
		
		if fail:
			for k in fail.childNodes:
				if k.nodeName == 'node':
					self.record(action(k), 'fail')
					self.fail.load(k)
					return
			raise Exception('Badly formed <fail> node')
	
