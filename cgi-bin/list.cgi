#!/usr/bin/env python

import cgitb; cgitb.enable()
import os
from urllib import quote
from glob import glob


print "Content-type:text/html"
print

epubs = glob("./*.epub")

for epub in epubs:
    path = os.path.relpath(epub, "./")
    print """<a href="epub-toc.cgi?path={0}">{1}</a><br>""".format(quote(path), path)

paths = ""
for epub in epubs:
    path = os.path.relpath(epub, "./")
    paths += "path={0}&".format(quote(path))

print """<br><a href="epub.cgi?{0}">viewall</a><br>""".format(paths)

