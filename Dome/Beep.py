class Beep(Exception):
	def __init__(self, message = None, may_record = 0):
		self.may_record = may_record
		if message: print "(Beep:%s)" % message
		self.message = message
	
	def __str__(self):
		if self.message:
			return "<Beep:%s>" % self.message
		else:
			return "<Beep!>"
