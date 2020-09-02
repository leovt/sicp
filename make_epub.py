import zipfile
import os
import mimetypes
from datetime import datetime
import uuid
from html.parser import HTMLParser
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup, Doctype
import sys
import toc
from media import Medium
import configparser

sys.setrecursionlimit(3000)

def relpath(arcname, base):
    a = arcname.split('/')
    b = base.split('/')

    while a and b and a[0] == b[0]:
        a = a[1:]
        b = b[1:]

    if not a:
        raise ValueError

    return '/'.join(['..']*(len(b)-1) + a)

class FindChildren(HTMLParser):
    '''
    A HTMLParser subclass to find related resources to download.

    while parsing, two sets are filled:
        self.download_only: urls of stylesheets and images
        self.follow: urls of html pages to follow (currently the "next" link only)
    '''
    def __init__(self):
        HTMLParser.__init__(self)
        self.download_only = set()
        self.follow = set()
        self.data = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            self.download_only.add(attrs['src'])
        if tag == 'a':
            self.a_href = attrs.get('href')
        if tag == 'link':
            if attrs['rel'] == 'stylesheet':
                self.download_only.add(attrs['href'])
        self.data = None

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.data == 'next':
                self.follow.add(self.a_href)
        #print("Encountered an end tag :", tag)

    def handle_data(self, data):
        self.data = data.strip()
        #print("Encountered some data  :", data)

class Document:
    def __init__(self, name):
        self.media = {}
        self.spine = []
        self.book_uuid = uuid.uuid4()

        self.title = 'Structure and Interpretation of Computer Programs, Second Edition'

        self.list_content(name)

    def list_content(self, name):
        while True:
            med = Medium(name=name, data=open(name).read())
            self.media[name] = med
            self.spine.append(med)
            parser = FindChildren()
            parser.feed(med.data)
            for ref in parser.download_only:
                absref = urljoin(name, ref)
                if os.path.exists(absref):
                    self.media[absref] = Medium(name=absref, data=open(absref, 'rb').read())
                else:
                    print(f'WARNING: {absref} not found locally')

            assert len(parser.follow) <= 1
            if not parser.follow:
                break

            ref = parser.follow.pop()
            name = urljoin(name, ref)

    def content_opf(self):
        AUTHOR = 'Harold Abelson and Gerald Jay Sussman with Julie Sussman'
        PUBLISHER = 'MIT Press'
        PUB_DATE = '1996-08-15'
        LANGUAGE = 'en-US'
        modified = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        metadata = f'''  <metadata>
    <dc:title>{self.title}</dc:title>
    <dc:creator>{AUTHOR}</dc:creator>
    <dc:identifier id="bookid">urn:uuid:{self.book_uuid}</dc:identifier>
    <dc:language>{LANGUAGE}</dc:language>
    <dc:date>{PUB_DATE}</dc:date>
    <dc:publisher>{PUBLISHER}</dc:publisher>
    <meta property="dcterms:modified">{modified}</meta>
    <meta name="cover" content="cover" />
  </metadata>'''


        items = []
        for med in self.media.values():
            attrs = {
                'href': med.name,
                'id': med.id,
                'media-type': mimetypes.guess_type(med.name)[0],
            }
            attrs.update(med.attributes)
            attrs=' '.join(f'{key}="{value}"' for key, value in attrs.items())
            items.append(f'    <item {attrs}/>')

        manifest = '  <manifest>\n' + '\n'.join(items) + '\n  </manifest>'

        itemrefs = [
            f'    <itemref idref="{med.id}"/>'
            for med in self.spine]

        spine = '  <spine toc="toc">\n' + '\n'.join(itemrefs) + '\n  </spine>'

        return f'''<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xml:lang="en" unique-identifier="bookid" version="3.0">
{metadata}
{manifest}
{spine}
</package>'''

    def toc_entries(self):
        for med in self.spine:
            soup = med.soup
            for tag in soup.find_all(re.compile(r'^h[1-3]$')):
                if tag.get('id'):
                    text = ' '.join(tag.stripped_strings)
                    yield toc.FlatTocInfo(med.name +'#' + tag['id'], text, int(tag.name[1:]))
                else:
                    print ('No ID for', tag)

    def set_cover(self, cover):
        self.media[cover].id = 'cover'
        self.media[cover].attributes['properties'] = 'cover-image'

    def replace_resources(self):
        config = configparser.ConfigParser()
        assert config.read('new_content/replace.ini')
        for fname in config.sections():
            arcname = config.get(fname, 'arcname')
            replaces = config.get(fname, 'replaces')
            self.media[replaces] = Medium(name=arcname,
                data=open('new_content/'+fname,'rb').read())

    def write(self, name):
        with zipfile.ZipFile(name, 'w') as archive:
            archive.writestr('mimetype', b'application/epub+zip')
            archive.writestr('META-INF/container.xml',
'''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml" />
  </rootfiles>
</container>
''')
            mytoc = toc.Toc()
            for item in self.toc_entries():
                mytoc.add(item)
            med = mytoc.ncx(self)
            self.media[med.name] = med
            med = mytoc.xhtml(self)
            self.media[med.name] = med
            content = self.content_opf()
            archive.writestr('content.opf', content)
            for med in self.media.values():
                assert isinstance(med.get_data(), (str, bytes)), med
                archive.writestr(med.name, med.get_data())

    def make_xml(self):
        for med in self.media.values():
            if med.name.endswith('.html'):
                print('transforming ', med.name)
                med.name = med.name[:-5] + '.xhtml'

                soup = BeautifulSoup(med.data, 'html5lib')

                rename_obsolete_tt_tag(soup)
                remove_obsolete_attributes(soup)
                remove_font_tag(soup)
                replace_inline_formula_images(soup)
                remove_navigation(soup)

                clean_epigraph_content(soup)
                clean_headers(soup)

                move_table_out_of_p_tag(soup)
                clean_caption_tags(soup)
                make_caption_first_child(soup)

                remove_toc_backlinks(soup)
                anchor_name_to_id_and_deduplicate(soup)
                move_anchors_from_ul_to_li(soup)
                move_anchor_id_to_header(soup)
                update_anchors_href(soup)
                remove_empty_p_tag(soup)

                for item in soup:
                    if isinstance(item, Doctype):
                        item.replace_with(Doctype('html'))
                        break

                soup.html['xmlns'] = 'http://www.w3.org/1999/xhtml'

                med.data = None
                med.soup = soup

    def update_links(self):
        for med in self.media.values():
            if med.name.endswith('.xhtml'):
                print('updating links in ', med.name)
                modified = False
                soup = med.soup
                for tag in soup.find_all('img'):
                    abs_src = urljoin(med.name, tag['src'])
                    referenced_media = self.media.get(abs_src)
                    if not referenced_media:
                        print('no content for', abs_src)
                        continue
                    if referenced_media.name != abs_src:
                        new_src = relpath(referenced_media.name, med.name)
                        print(tag['src'], '->', new_src)
                        tag['src'] = new_src
                        modified = True
                if modified:
                    med.data = soup.prettify()

    def remove_unused_images(self):
        to_remove = [x for x in self.media
            if re.match(r'^book/book-Z-G-D-(\d+).gif$', x)]
        for name in to_remove:
            del self.media[name]



def rename_obsolete_tt_tag(soup):
    for tag in soup.find_all('tt'):
        tag.name = 'code'

def remove_empty_p_tag(soup):
    for tag in soup.find_all('p'):
        is_empty = True
        for x in tag.contents:
            if x.name:
                is_empty = False
                break
            elif x.strip():
                is_empty = False
                break
        if is_empty:
            tag.decompose()

def anchor_name_to_id_and_deduplicate(soup):
    ids = set()
    for tag in soup.find_all('a'):
        if 'name' in tag.attrs:
            new_id = tag['name'].replace('%', 'a')
            if new_id in ids:
                print('Duplicate ID', tag)
                tag.decompose()
            else:
                tag['id'] = new_id
                ids.add(new_id)
                del tag['name']

def clean_caption_tags(soup):
    for tag in soup.find_all('caption'):
        if tag.div:
            tag.div.unwrap()
        del tag['align']

def move_table_out_of_p_tag(soup):
    for tag in soup.find_all('table'):
        if tag.parent.name == 'p':
            p_before = tag.parent
            p_after = soup.new_tag('p')
            for child in list(tag.next_siblings):
                p_after.append(child)
            p_before.insert_after(tag)
            p_before.insert_after(p_after)

def clean_headers(soup):
    for tag in soup.find_all(re.compile(r'^h\d$')):
        if tag.div:
            tag.div.unwrap()
        if tag.p:
            tag.p.unwrap()
        if tag.code:
            tag.code.unwrap()

def clean_epigraph_content(soup):
    for tag in soup.find_all(**{'class': 'epigraph'}):
        div = tag.parent.parent.parent.parent.parent
        assert div.name == 'div'
        #print('='*60)
        #print(div)
        div['class'] = tag['class']
        div.table.tbody.tr.td.span.unwrap()
        div.table.tbody.tr.td.unwrap()
        div.table.tbody.tr.unwrap()
        div.table.tbody.unwrap()
        div.table.unwrap()
        #print('-'*60)
        #print(div)

def make_caption_first_child(soup):
    for tag in soup.find_all('caption'):
        table = tag.parent
        assert table.name == 'table'
        table.insert(0, tag)

def remove_font_tag(soup):
    for tag in soup.find_all('font'):
        tag.unwrap()

def remove_toc_backlinks(soup):
    for tag in soup.find_all('a', href=re.compile(r'%_toc_%')):
        tag.unwrap()

def update_anchors_href(soup):
    for tag in soup.find_all('a'):
        if 'href' in tag.attrs:
            href = tag['href']
            i = href.find('#')
            if i == -1:
                i = len(href)
            href_new = href[:i].replace('.html', '.xhtml') + href[i:].replace('%', 'a')
            if href_new != href:
                #print(href, '->', href_new)
                tag['href'] = href_new

def remove_obsolete_attributes(soup):
    for tag in soup.find_all('div'):
        del tag['align']

    for tag in soup.find_all('td'):
        del tag['valign']

    for tag in soup.find_all('table'):
        del tag['width']
        del tag['border']

    for tag in soup.find_all('img'):
        del tag['border']


def replace_inline_formula_images(soup):
    for tag in soup.find_all('img'):
        match = re.match(r'^book-Z-G-D-(\d+).gif$', tag['src'])
        if match:
            REPLACEMENTS = {
                '3': 'Θ', '4': 'θ', '6': 'λ',
                '9': 'π', '11': 'ϕ', '12': 'ψ',
                '13': '√',
                '14': '←', '15': '→', '16': '↑', '17': '↦',
                '18': '⋮', '19': '∫', '20': '≈',
            }
            tag.replace_with(REPLACEMENTS[match.group(1)])

def move_anchors_from_ul_to_li(soup):
    for tag in soup.find_all('a'):
        if tag.parent.name == 'ul':
            tag.parent.li.insert(0, tag)

def move_anchor_id_to_header(soup):
    for tag in soup.find_all(re.compile(r'^h\d$')):
        walk = tag
        while True:
            walk = walk.previous_sibling
            if walk.name == 'a':
                anchor = walk
                break
            elif walk.name == 'p' and walk.a is not None:
                anchor = list(walk.find_all('a'))[-1]
                break
            elif walk is None or (walk.string or '').strip():
                anchor = None
                break
        if not anchor:
            print('Could not find anchor for', tag)
            continue
        id_ = anchor.get('id')
        if id_ and (id_.startswith('a_chap') or id_.startswith('a_sec')):
            tag['id'] = id_
            anchor.unwrap()
        else:
            print('Found anchor but no id', anchor, tag)

def remove_navigation(soup):
    for tag in soup.find_all('div', **{'class': 'navigation'}):
        tag.decompose()

def main():
    doc = Document('book/book.html')
    doc.make_xml()
    doc.replace_resources()
    doc.remove_unused_images()
    doc.set_cover('book/cover.jpg')
    doc.update_links()
    doc.write('sicp.epub')

if __name__ == '__main__':
    main()
