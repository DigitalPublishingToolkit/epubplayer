#!/usr/bin/env python

import cgitb; cgitb.enable()
import cgi, os, epub, json, sys, html5lib
from xml.etree import ElementTree as ET 
from urllib import quote
from settings import EPUB_PATH


def split_fragment (href):
    if '#' in href:
        return href.split("#", 1)
    else:
        return (href, "")


def annotated_spine(book):
    """ annotate the spine with the table of contents for labels and eventual subdivisions """  

    toc = []

    def split_fragment (href):
        if '#' in href:
            return href.split("#", 1)
        else:
            return (href, "")

    def _np (np, depth=0):
        ret = {'depth': depth}
        ret['label'], _lang, _dir = np.labels[0]
        ret['src'] = np.src
        ret['src_nofragment'], ret['fragment'] = split_fragment(np.src)
        return ret

    def _walk (np, depth=0):
        for child in np:
            toc.append(_np(child))
            _walk(child.nav_point, depth+1)
    _walk(book.toc.nav_map.nav_point)

    ret = []
    for itemref, linear in book.opf.spine.itemrefs:
        item = book.get_item(itemref)
        matches = [x for x in toc if x['src_nofragment'] == item.href]
        if len(matches) == 0:
            ret.append({'src': item.href, 'src_nofragment': item.href, 'fragment': '', 'label': u'', 'depth': 0})
        else:
            for m in matches:
                ret.append(m)
    return ret

fs = cgi.FieldStorage()
cmd = fs.getvalue("c", "list")
paths = [x.strip("/") for x in fs.getlist("path")]

if EPUB_PATH:
    pwd = EPUB_PATH
else:
    pwd = os.environ.get("PATH_TRANSLATED", ".")
fullpaths = [os.path.join(pwd, x) for x in paths]

def view_link (path, href):
    href, fragment = split_fragment(href)
    ret = "/cgi-bin/epub.cgi?c=view&path={0}&href={1}".format(path, href)
    if fragment:
        ret += "#"+fragment
    return ret
               
if cmd == 'json':
    ###################
    # TOC 
    ###################

    epubs = [epub.open_epub(path) for path in fullpaths]
    data = {}
    data['books'] = []

    for epub, path in zip(epubs, paths):
        book = {}
        data['books'].append(book)
        book['path'] = path
        book['title'] = epub.opf.metadata.titles[0][0]

        cover = None
        for name, value in epub.opf.metadata.metas:
            if name == "cover":
                citem = epub.get_item(value)
                if citem:
                    book['cover'] = view_link(path, citem.href)
                else:
                    # ATTEMPT TO PULL COVER FROM TITLE PAGE
                    # OR... use first image in spine?
                    for _id, item in epub.opf.manifest.iteritems():
                        if item.media_type == "image/jpeg" or item.media_type == "image/png":
                            book['cover'] = view_link(path, item.href)
                            break

        def _nav_point (np, depth=0):
            ret = []
            for child in np:
                item = {}
                label, lang, _dir = child.labels[0]
                item['label'] = label
                item['src'] = child.src
                href, fragment = split_fragment(child.src)
                link = "/cgi-bin/epub.cgi?c=view&path={0}&href={1}".format(path, href)
                if fragment:
                    link += "#"+fragment
                item['link'] = link
                item['depth'] = depth
                ret.append(item)
                item['children'] = _nav_point(child.nav_point, depth+1)
            return ret
        book['toc'] = _nav_point(epub.toc.nav_map.nav_point)

        def link (item):
            link = "/cgi-bin/epub.cgi?c=view&path={0}&href={1}".format(path, item['src_nofragment'])
            if item['fragment']:
                link += "#"+item['fragment']
            item['link'] = link
            return item

        book['annotated_spine'] = [link(x) for x in annotated_spine(epub)]

    print "Content-type: application/json"
    print
    print json.dumps(data)
    sys.exit(0)

elif cmd == 'view':

    ########################################
    ### ITEM VIEW
    ########################################

    epubs = [epub.open_epub(path) for path in fullpaths]
    book = epubs[0]
    href = fs.getvalue("href", "")
    href, fragment = split_fragment(href) # shouldn't happen but just in case...
    item = book.get_item_by_href(href)

    print "Content-type: {0}".format(item.media_type)
    print
    if item.media_type == "application/xhtml+xml":
        # (X)HTML page: remap links
        content = book.read_item(item).decode("utf-8")
        t = html5lib.parse(content, namespaceHTMLElements=False)
        # t = ET.fromstring(item.content)
        for l in t.findall(".//*[@href]"):
            if not l.attrib['href'].startswith("#"):
                href = l.attrib['href']
                hrefnofrag, frag = split_fragment(href)
                check_item = book.get_item_by_href(hrefnofrag)
                if check_item != None:
                # href = urljoin(item.href, l.attrib['href'])
                    if frag:
                        l.attrib['href'] = "?c=view&path={0}&href={1}#{2}".format(quote(fs.getvalue("path")), quote(hrefnofrag), frag)
                    else:
                        l.attrib['href'] = "?c=view&path={0}&href={1}".format(quote(fs.getvalue("path")), quote(href))

        for l in t.findall(".//*[@src]"):
            # src = urljoin(item.href, l.attrib['src'])
            src = l.attrib['src']
            srcnofrag, frag = split_fragment(src)
            # l_id = epub.id_for_href(src)
            check_item = book.get_item_by_href(srcnofrag)
            if check_item != None:
                l.attrib['src'] = "?c=view&path={0}&href={1}".format(quote(fs.getvalue("path")), quote(src))

        print ET.tostring(t, method="xml")

    else:
        # else: serve file as is
        content = book.read_item(item)
        print content
    sys.exit(0)

else:

    ##########################
    ### MAIN VIEW
    ##########################

    print "Content-type:text/html;charset=utf-8"
    print
    print """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>epubplayer</title>
<link rel="stylesheet" type="text/css" href="/epub.css" />
</head>
<body>
<div id="player"></div>
</body>
<script src="/lib/jquery.min.js"></script>
<script src="/lib/d3.min.js"></script>
<script src="/epub.js"></script>
</html>

"""

