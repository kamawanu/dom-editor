from xml.dom.ext.reader import HtmlLib, Sgmlop

class Reader(HtmlLib.Reader):
	def __init__(self):
		self.parser = MyHtmlParser()

class MyHtmlParser(Sgmlop.HtmlParser):
	def handle_special(self, data):
		print "handle_special: ignored '" + data + "'"
