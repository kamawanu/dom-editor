def debug_prompt(signum, frame):
	import readline, traceback
	print "Debug mode! 'view' and 'model' are the last created View and Models."
	while 1:
		line = raw_input("(debug) ")
		try:
			try:
				_ = eval(line, globals(), locals())
				if _ is not None:
					print _
			except:
				exec line
		except:
			traceback.print_exc()
