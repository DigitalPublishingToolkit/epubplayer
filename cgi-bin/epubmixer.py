from __future__ import print_function
import os, sys, zipfile, datetime
from xml.etree import ElementTree as ET 
from urlparse import urljoin, urlparse, parse_qs
from shutil import copytree, rmtree
from uuid import uuid1


EPUB3_TEMPLATE_PATH = "cgi-bin/epub3_template"

NS = {}
NS['opf'] = "http://www.idpf.org/2007/opf"
NS['epub'] = "http://www.idpf.org/2007/ops"
NS['dc'] = "http://purl.org/dc/elements/1.1/"
NS['xhtml'] = "http://www.w3.org/1999/xhtml"

# todo? Create read only state that isn't (necessarily) unzipped ?!
# Expand zip directly into new file ?!

class EPUBRipper:
    def __init__(self, path, open=True, verbose=False):
        path_noext, ext = os.path.splitext(path)
        self.verbose = verbose
        if ext.lower() == ".epub":
            self.epub_path = path
            self.path = path_noext
        else:
            self.path = path
            self.epub_path = path.rstrip("/")+".epub"
        
        if open:
            self.open()

    def log (self, *msgs):
        if self.verbose:
            print (*msgs, file=sys.stderr)

    def open (self):
        if os.path.exists(self.path):
            self.read_from_path()
        elif os.path.exists(self.epub_path):
            self.unzip()
            self.read_from_path()
        else:
            # initialize empty book
            self.log("init empty book")
            copytree(EPUB3_TEMPLATE_PATH, self.path)
            self.read_from_path()
            # Generate a UUID dc:identifier
            dc_id = self._child(self.metadata, "dc:identifier", create=True)
            dc_id.text = "urf:uuid:{0}".format(uuid1())
            dc_id.attrib['id'] = "epub-id"
            # TIMESTAMPS
            now = datetime.datetime.now()
            # Generate a dc:date
            dc_date = self._child(self.metadata, "dc:date", create=True)
            dc_date.attrib['id'] = "epub-date"
            dc_date.text = now.strftime("%Y-%m-%d")
            # Generate a lastmodified meta
            lastmod = self._child(self.metadata, "opf:meta", create=True)
            lastmod.attrib['property'] = "dcterms:modified"
            lastmod.text = now.isoformat()

    def ensure_path (self):
        """ Make the self.path directory if necessary """
        try:
            os.mkdir(self.path)
            self.log("mkdir", self.path)
        except OSError, e:
            pass

    def unzip (self):
        """ Expand .epub into directory
        NB: does not remove previous folder contents """
        with zipfile.ZipFile(self.epub_path, "r") as z:
            self.ensure_path()
            z.extractall(self.path)

    def zip (self):
        """ Refresh the .epub from directory contents
        NB: Overwrites any existing epub """
        contents = []
        for base, dirs, files in os.walk(self.path):
            for f in files:
                path = os.path.join(base, f)
                rpath = os.path.relpath(path, self.path)
                contents.append(rpath)
        contents.sort()
        contents.remove("mimetype")
        with zipfile.ZipFile(self.epub_path, "w") as zout:
            zout.write(os.path.join(self.path, "mimetype"), "mimetype", zipfile.ZIP_STORED)
            for c in contents:
                zout.write(os.path.join(self.path, c), c, zipfile.ZIP_DEFLATED)

    def _child (self, elt, qname, create=False):
        """Get (and optionally create) a child element of elt specified by qname, of form ns:tag, e.g. dc:title"""
        ns, tag = qname.split(":")
        qtagname = "{"+NS[ns]+"}"+tag
        ret = elt.find("./"+qtagname)
        if ret == None and create:
            self.log("creating tag", qname)
            ret = ET.SubElement(elt, qtagname)
        return ret

    def set_title (self, title):
        self.title = title
        dc_title = self._child(self.metadata, "dc:title", create=True)
        dc_title.attrib['id'] = "epub-title"
        dc_title.text = title

    def read_from_path (self):
        """ Sync object data from path """
        # Locate content.opf
        self.container = ET.parse(open(os.path.join(self.path, "META-INF/container.xml")))
        rootfile = self.container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        self.content_path = rootfile.attrib.get("full-path")
        self.log("Got content_path", self.content_path)

        # muy importante (for output/rewrite)
        ET.register_namespace('',"http://www.idpf.org/2007/opf")
        self.content = ET.parse(open(os.path.join(self.path, self.content_path)))
        # self.content.register_namespace("", "http://www.idpf.org/2007/opf")
        self.package = self.content.getroot()
        self.metadata = self._child(self.package, "opf:metadata")
        self.manifest = self._child(self.package, "opf:manifest")
        self.spine = self._child(self.package, "opf:spine")
        self.guide = self._child(self.package, "opf:guide")

        dc_title = self._child(self.metadata, "dc:title")
        if dc_title != None:
            self.title = dc_title.text

    def write_to_path (self):
        """ Sync everything to files """
        ET.register_namespace('',"http://www.idpf.org/2007/opf")
        content_path = os.path.join(self.path, self.content_path)
        with open(content_path, "w") as f:
            self.content.write(f, xml_declaration=True, encoding="utf-8", method="xml")
            # f.write(ET.tostring(self.content.getroot(), method="xml"))

    def path_for_href(self, href):
        return os.path.join(self.path, urljoin(self.content_path, href))

    def _q (self, qname):
        ns, tag = qname.split(":", 1)
        return "{"+NS[ns]+"}"+tag

    def get_item_by_href(self, href):
        for item in self.manifest.findall("./"+self._q("opf:item")):
            ihref = item.attrib.get("href")
            if ihref == href:
                return EPUBRipperItem(self, item)

    def read_item (self, href):
        path = self.path_for_href(href)
        with open(path) as f:
            contents = f.read()
            return contents

    def write_item (self, href, data):
        path = self.path_for_href(href)
        with open(path, "w") as f:
            f.write(data)
            return len(data)

    def import_item (self, srcitem, importLinkedItems=True, appendToSpine=True, toc=True):
        """ Adds item and linked items to this epub as a manifested item + file.
        importLinkedItems means that any linked item (such as a stylesheet or linked page) will
        also be imported and mapped to a local item.
        Returns: Item local to this epub, NB: Item still needs to be evt. explicitly added to the spine / toc.
        """
        new_item_elt = ET.SubElement(self.manifest, self._q("opf:item"))
        new_item_elt.attrib['id'] = srcitem.id
        new_item_elt.attrib['href'] = srcitem.href
        new_item_elt.attrib['media-type'] = srcitem.media_type
        new_item = EPUBRipperItem(self, new_item_elt)

        item_contents = srcitem.get_contents()
        new_item.set_contents(item_contents)

        if appendToSpine:
            self.append_item_to_spine(new_item)
        return new_item


    def append_item_to_spine (self, item, linear=True):
        spine_elt = ET.SubElement(self.spine, self._q("opf:itemref"))
        spine_elt.attrib['idref'] = item.id
        if not linear:
            spine_elt.attrib['linear'] = "no"
        return spine_elt

        # copy file from srcitem.epub
        # add to manifest
        # map src.epub+href => this.href , and remember this mapping
        # auto-import linked items, mapping these as well
        # finally add element to the spine ? (or just return a (local) item ref that can then be added to spine)


class EPUBRipperItem (object):

    def __init__(self, epub, item_elt):
        self.epub = epub
        self.elt = item_elt
        self.href = item_elt.attrib.get("href")
        self.id = item_elt.attrib.get("id")
        self.media_type = item_elt.attrib.get("media-type")

    def get_contents (self):
        return self.epub.read_item(self.href)

    def set_contents(self, data):
        return self.epub.write_item(self.href, data)

def mixbooks (playlist, src_path, output_path = "bookmarks.epub"):
    mixepub = EPUBRipper(output_path, verbose=False)
    mixepub.set_title("Bookmarks {0}".format(datetime.datetime.today().strftime("%A %d %B %Y")))
    books = {}

    # todo: prevent collisions!
    def href_for (item):
        return item.href

    # todo: prevent collisions!
    def id_for (item):
        return item.identifier

    for epubref in playlist.strip().splitlines():
        parts = urlparse(epubref)
        ref_path = os.path.join(src_path, parts.path)
        if ref_path not in books:
            books[ref_path] = EPUBRipper(ref_path, verbose=False)
        href = parse_qs(parts.query).get("href")[0]
        item = books[ref_path].get_item_by_href(href)
        if item == None:
            print ("item not found", href)
        
        mixepub.import_item(item)

    mixepub.write_to_path()
    mixepub.zip()
    rmtree(mixepub.path)


if __name__ == "__main__":
    # path = sys.argv[1]
    # epub = EPUBRipper(path, verbose=True)

    # epub.open_content()
    # # remove the title page
    # # <itemref idref="title_page_xhtml" linear="no" />
    # titleref = epub.spine.find('.//{http://www.idpf.org/2007/opf}itemref[@idref="title_page_xhtml"]')
    # epub.spine.remove(titleref)
    # replace_toc(epub, "nav", "ch002_xhtml")
    # patch_footnotes(epub)
    # epub.rewrite_content()

    playlist = """SotQreader.epub?href=ch005.xhtml
unlike-us-reader.epub?href=unlike-us-reader-14.xhtml#toc_marker-13"""
    mixbooks(playlist, src_path="..", output_path="../bookmarks.epub")
