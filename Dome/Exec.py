from gtk import *
from support import *

from Beep import Beep
from Macro import MacroNode

# An exec represents an executing macro, including the stack, root and cursor position

class Exec:
	def __init__(self, view):
		self.view = view
		
		# Which node we have just left and which exit we took
		self.where = None
		self.exit = None
		
		self.sched_tag = 0
		self.stack = []
		self.clean()
	
	def running(self):
		return self.sched_tag != 0
	
	def freeze(self):
		self.frozen = 1
	
	def unfreeze(self, exit):
		self.frozen = 0
		if not self.frozen:
			node = getattr(self.where, self.exit)
			if exit == 'fail':
				self.last_fail_node = node
			self.set_pos(node, exit)
			if self.stop_after < 0 or self.stop_after > 1:
				self.sched()

	def clean(self):
		"Return to a clean state (empty stack; no point)"
		self.doing_node = None	# Node being executed right now
		self.frozen = 0
		self.set_pos(None)
		self.unstack_n(len(self.stack))

		self.stop_after = -1

		if self.sched_tag:
			idle_remove(self.sched_tag)
			self.sched_tag = 0
	
	# stop_after values:
	# -1  -  never stop
	#  0  -  stop after one operation
	#  1  -  stop after one operation, increment on play
	#  n  -  decrement on return
	# Also unfreezes...
	def set_step_mode(self, stop_after):
		self.frozen = 0
		self.stop_after = stop_after

	def rec_cb(self, choice):
		if choice == 0:
			self.view.toggle_record(extend = TRUE)
			self.where.macro.show_all()
	
	def play(self, macro_name, when_done = None):
		"When macro returns call when_done(), if given."
		self.frozen = 0

		m = self.view.model.macro_list.macro_named(macro_name)
		if not m:
			raise Exception('No macro named `' + macro_name + "'!")

		if self.doing_node:
			self.stack.append(self.doing_node)
			self.doing_node.highlight('cyan')
			self.doing_node = None

		if when_done:
			self.stack.append(when_done)

		self.set_pos(m.start)

		print "stop_after", self.stop_after

		if self.stop_after == 0:
			m.show_all()
			return
			
		if self.stop_after > 0:
			self.stop_after += 1
		self.sched()
	
	def set_pos(self, node, exit = 'next', how_far = 0.9):
		"Set the node which we have just exited, and which way we left."
		if self.where:
			self.where.set_exec_point(None)
		self.where = node
		self.exit = exit
		if node:
			node.set_exec_point(exit, how_far)
	
	def stop(self):
		if self.sched_tag:
			idle_remove(self.sched_tag)
		
	def sched(self):
		self.stop()
		self.sched_tag = idle_add(self.idle_cb)
		print "Sched..."
	
	def idle_cb(self):
		if not self.frozen:
			self.do_one_step()

		if self.where and \
		  (self.stop_after < 0 or self.stop_after > 1) and \
		  not self.frozen:
			return 1

		self.sched_tag = 0
		return 0
	
	def do_one_step(self):
		# Where we are and where we're going...
		current = self.where
		
		if not current:
			raise Exception('No macro is currently executing!')

		next = getattr(current, self.exit)
		if not next:
			# Move, but don't actually execute anything (helps with single-stepping)
			self.up_the_stack()
			return
			
		action = next.action

		self.doing_node = next
		try:
			try:
				self.view.do_action(action)
				dir = 'next'
			except Beep:
				dir = 'fail'
				self.last_fail_node = next
		finally:
			self.doing_node = None

		if current != self.where or self.frozen:
			return	# Something has moved us already ('playback'?)

		self.set_pos(next, dir)

	# Unhighlight n nodes, popping then from the stack as we go.
	def unstack_n(self, n):
		# XXX: Recursion won't unhighlight correctly...
		while n > 0:
			node = self.stack.pop()
			if isinstance(node, MacroNode):
				node.highlight('blue')
			n -= 1
			if self.stop_after > 0:
				self.stop_after -= 1

	# Current node doesn't have an exit in the right direction.
	# Move the point up the stack (one frame max).
	def up_the_stack(self):
		if self.stack:
			# Up the stack and try again with the same exit later
			new = self.stack[-1]
			self.unstack_n(1)
			print "Up to", new
			if callable(new):
				if self.exit == 'next':
					new()
				else:
					return self.up_the_stack()
			else:
				self.set_pos(new, self.exit)
			return

		# We can't go up... now what?

		if self.exit == 'next':
			# We're done - success!
			print "Done!"
			self.set_pos(None)
			return

		# Give up and fail on the innermost node
		print "Compete failure!"
		gdk_beep()
		self.stop_after = 0
		self.set_pos(self.last_fail_node, 'fail')
		if self.view.recording_where == None:
			get_choice("Macro execution failed - record failure case?",
					self.where.macro.uri,
					('Record', 'No'),
					callback = self.rec_cb)
		else:
			self.where.macro.show_all()
