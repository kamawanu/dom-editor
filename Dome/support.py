import sys
from traceback import format_exception_only

from string import find, lower, join
from socket import gethostbyaddr, gethostname

from gtk import *

bad_xpm = [
"12 12 3 1",
" 	c #000000000000",
".	c #FFFF00000000",
"X	c #FFFFFFFFFFFF",
"            ",
" ..XXXXXX.. ",
" ...XXXX... ",
" X...XX...X ",
" XX......XX ",
" XXX....XXX ",
" XXX....XXX ",
" XX......XX ",
" X...XX...X ",
" ...XXXX... ",
" ..XXXXXX.. ",
"            "]

def load_pixmap(window, path):
	try:
		p, m = create_pixmap_from_xpm(window, None, path)
	except:
		print "Warning: failed to load icon '%s'" % path
		p, m = create_pixmap_from_xpm_d(window, None, bad_xpm)
	return p, m

_host_name = None
def our_host_name():
	global _host_name
	if _host_name:
		return _host_name
	(host, alias, ips) = gethostbyaddr(gethostname())
	for name in [host] + alias:
		if find(name, '.') != -1:
			_host_name = name
			return name
	return name
	
def get_local_path(uri):
	"Convert uri to a local path and return, if possible. Otherwise,"
	"return None."
	host = our_host_name()

	if not uri:
		return None

	if uri[0] == '/':
		if uri[1] != '/':
			return uri	# A normal Unix pathname
		i = find(uri, '/', 2)
		if i == -1:
			return None	# //something
		if i == 2:
			return uri[2:]	# ///path
		remote_host = uri[2:i]
		if remote_host == host:
			return uri[i:]	# //localhost/path
		# //otherhost/path
	elif lower(uri[:5]) == 'file:':
		if uri[5:6] == '/':
			return get_local_path(uri[5:])
	elif uri[:2] == './' or uri[:3] == '../':
		return uri
	return None

# Open a modal dialog box showing a message.
# The user can choose from a selection of buttons at the bottom.
# Returns -1 if the window is destroyed, or the number of the button
# if one is clicked (starting from zero).
#
# If a dialog is already open, returns -1 without waiting AND
# brings the current dialog to the front.
current_dialog = None
def get_choice(message, title, buttons):
	global current_dialog, choice_return

	if current_dialog:
		current_dialog.hide()
		current_dialog.show()
		return -1

	current_dialog = GtkWindow(WINDOW_DIALOG)
	current_dialog.unset_flags(CAN_FOCUS)
	current_dialog.set_modal(TRUE)
	current_dialog.set_title(title)
	current_dialog.set_position(WIN_POS_CENTER)
	current_dialog.set_border_width(2)

	vbox = GtkVBox(FALSE, 0)
	current_dialog.add(vbox)
	action_area = GtkHBox(TRUE, 5)
	action_area.set_border_width(2)
	vbox.pack_end(action_area, FALSE, TRUE, 0)
	vbox.pack_end(GtkHSeparator(), FALSE, TRUE, 2)

	text = GtkLabel(message)
	text.set_line_wrap(TRUE)
	text_container = GtkEventBox()
	text_container.set_border_width(40)	# XXX
	text_container.add(text)

	vbox.pack_start(text_container, TRUE, TRUE, 0)

	default_button = None
	n = 0
	for b in buttons:
		label = GtkLabel(b)
		label.set_padding(16, 2)
		button = GtkButton()
		button.add(label)
		button.set_flags(CAN_DEFAULT)
		action_area.pack_start(button, TRUE, TRUE, 0)
		def cb(widget, n = n):
			global choice_return
			choice_return = n
		button.connect('clicked', cb)
		if not default_button:
			default_button = button
		n = n + 1
		
	default_button.grab_focus()
	default_button.grab_default()
	action_area.set_focus_child(default_button)

	def cb(widget):
		global choice_return
		choice_return = -1
	current_dialog.connect('destroy', cb)

	choice_return = -2

	current_dialog.show_all()

	while choice_return == -2:
		mainiteration(TRUE)

	retval = choice_return

	if retval != -1:
		current_dialog.destroy()

	current_dialog = None

	return retval

def report_error(message, title = 'Error'):
	return get_choice(message, title, ['OK'])

def report_exception():
	ex = format_exception_only(sys.exc_type, sys.exc_value)
	report_error(join(ex, ''))
