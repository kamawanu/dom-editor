# Due to a shocking number of bugs and incompatibilities between PyXML and 4Suite,
# this actually seems to be the easiest way to convert a XML document to HTML!

import sys
from xml.dom.html import HTMLDocument
from Ft.Xml.cDomlette import implementation
from Ft.Xml.Xslt.Processor import Processor
from Ft.Xml import InputSource
doc = implementation.createDocument(None, 'root', None)
proc = Processor()
from cStringIO import StringIO
stream = StringIO('''
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html"/>

  <xsl:template match='@*|node()'>
    <xsl:copy>
      <xsl:apply-templates select='@*|node()'/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
''')
proc.appendStylesheet(InputSource.InputSource(stream))

def to_html(doc):
	return proc.runNode(doc, None, ignorePis = 1)
