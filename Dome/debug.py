import signal

def int_handler(signum, frame):
	import readline, traceback
	print "Debug mode! 'view' and 'model' are the last created View and Models."
	while 1:
		line = raw_input("(debug) ")
		try:
			try:
				a = eval(line, globals(), locals())
				if a is not None:
					print a
			except:
				exec line
		except:
			traceback.print_exc()
	
signal.signal(signal.SIGINT, int_handler)
