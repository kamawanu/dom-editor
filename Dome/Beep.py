class Beep(Exception):
	def __init__(self, may_record = 0):
		self.may_record = may_record
	
	def __str__(self):
		return "<Beep!>"
