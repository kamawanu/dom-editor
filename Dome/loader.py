import string

from gtk import *
from GDK import *

from rox.support import get_local_path

TARGET_URILIST = 0
TARGET_RAW = 1

def extract_uris(data):
	lines = string.split(data, '\r\n')
	out = []
	for l in lines:
		if l and l[0] != '#':
			out.append(l)
	return out

def drag_data_received(widget, context, x, y, selection_data, info, time, win):
	if info == TARGET_RAW:
		win.load_data(selection_data.data)
	else:
		uris = extract_uris(selection_data.data)
		if not uris:
			win.error("Nothing to load!")
			return
		paths = []
		remote = []
		for uri in uris:
			path = get_local_path(uri)
			if path:
				win.load_file(path)
			else:
				remote.append(uri)
		if remote:
			win.error("Can't load remote files yet!")

# 'widget' is the GTK widget that will accept drops
# 'window' provides 'load_file' and 'load_data' methods.
def make_xds_loader(widget, window):
	widget.drag_dest_set(DEST_DEFAULT_ALL,
			[('text/uri-list', 0, TARGET_URILIST),
			 ('text/plain', 0, TARGET_RAW),
			 ('application/octet-stream', 0, TARGET_RAW)
			],
			ACTION_COPY | ACTION_PRIVATE)
	
	widget.connect('drag_data_received', drag_data_received, window)
