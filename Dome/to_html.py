# Due to a shocking number of bugs and incompatibilities between PyXML and 4Suite,
# this actually seems to be the easiest way to convert a XML document to HTML!

# (note: moved to XHTML now anyway)
# Validates the output.

import sys
from xml.dom.html import HTMLDocument
from Ft.Xml.cDomlette import implementation
from Ft.Xml.Xslt.Processor import Processor
from Ft.Xml import InputSource
doc = implementation.createDocument(None, 'root', None)
proc = Processor()
from cStringIO import StringIO

# The HTML writer adds some header fields, so strip any existing ones out or we'll get
# two lots...

stream = StringIO('''
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
			      xmlns:h="http://www.w3.org/1999/xhtml">
<xsl:output method="xml" encoding="utf-8"
	doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
	doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"/>

  <xsl:template match='/h:html/h:head/h:meta[@name="generator"]' priority='2'/>
  <xsl:template match='/h:html/h:head/h:meta[@http-equiv="Content-Type"]'/>

  <xsl:template match='@*|node()'>
    <xsl:copy>
      <xsl:apply-templates select='@*'/>
      <xsl:apply-templates/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
''')
proc.appendStylesheet(InputSource.InputSource(stream))

def to_html(doc):
	import os, rox
	import traceback
	data = proc.runNode(doc, None, ignorePis = 1)
	cin, cout = os.popen4('xmllint --postvalid --noout -')
	cin.write(data)
	cin.close()
	results = cout.read()
	if results.strip():
		rox.alert(results)
	return data
