#!/usr/bin/env python

import cgitb; cgitb.enable()
import os
from urllib import quote
from glob import glob

print "Content-type: text/html"
print
epubs = glob("./*.epub")
paths = ""
for epub in epubs:
    path = os.path.relpath(epub, "./")
    paths += "path={0}&".format(quote(path))

print """<a href="/cgi-bin/epub.cgi?{0}">view all</a>""".format(paths)

