import zipfile
import os
import mimetypes
from itertools import count
from datetime import datetime
import uuid
from html.parser import HTMLParser
from urllib.parse import urljoin
from dataclasses import dataclass
import re
from bs4 import BeautifulSoup
import sys

sys.setrecursionlimit(3000)

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

@dataclass
class Medium:
    name: str
    data: str

class Document:
    def __init__(self, name):
        self.reference_updates = {
            'https://i.creativecommons.org/l/by-sa/4.0/88x31.png': 'cc-by-sa.png'
        }

        self.media = {}
        self.spine = []
        self.book_uuid = uuid.uuid4()

        self.list_content(name)

    def list_content(self, name):
        while True:
            med = Medium(name=name, data=open(name).read())
            self.media[name] = med
            self.spine.append(med)
            parser = FindChildren()
            parser.feed(med.data)
            for ref in parser.download_only:
                if ref in self.reference_updates:
                    ref = self.reference_updates[ref]
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
        TITLE = 'Structure and Interpretation of Computer Programs, Second Edition'
        AUTHOR = 'Harold Abelson and Gerald Jay Sussman with Julie Sussman'
        PUBLISHER = 'MIT Press'
        PUB_DATE = '1996-08-15'
        LANGUAGE = 'en-US'
        modified = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        metadata = f'''  <metadata>
    <dc:title>{TITLE}</dc:title>
    <dc:creator>{AUTHOR}</dc:creator>
    <dc:identifier id="bookid">urn:uuid:{self.book_uuid}</dc:identifier>
    <dc:language>{LANGUAGE}</dc:language>
    <dc:date>{PUB_DATE}</dc:date>
    <dc:publisher>{PUBLISHER}</dc:publisher>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>'''

        ids = (f'item{n}' for n in count(1000))

        id_for_media = {
            med.name: next(ids) for med in self.media.values()}

        items = [
            f'    <item href="{name}" id="{id_}" media-type="{mimetypes.guess_type(name)[0]}"/>'
            for name, id_ in id_for_media.items()]

        manifest = '  <manifest>\n' + '\n'.join(items) + '\n  </manifest>'

        itemrefs = [
            f'    <itemref idref="{id_for_media[med.name]}"/>'
            for med in self.spine]

        spine = '  <spine>\n' + '\n'.join(itemrefs) + '\n  </spine>'

        return f'''<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xml:lang="en" unique-identifier="bookid" version="3.0">
{metadata}
{manifest}
{spine}
</package>'''

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
            content = self.content_opf()
            archive.writestr('content.opf', content)
            with open('content.opf', 'w') as dummy:
                dummy.write(content)
            for med in self.media.values():
                assert isinstance(med.data, (str, bytes)), med
                archive.writestr(med.name, med.data)



    def make_xml(self):
        for med in self.media.values():
            if med.name.endswith('.html'):
                print('transforming ', med.name)
                med.name = med.name[:-5] + '.xhtml'
                OLD_DOCTYPE = '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">'
                NEW_DOCTYPE = '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>'

                soup = BeautifulSoup(med.data, 'html5lib')

                rename_obsolete_tt_tag(soup)
                remove_obsolete_attributes(soup)
                remove_font_tag(soup)
                replace_inline_formula_images(soup)

                clean_epigraph_content(soup)
                clean_headers(soup)

                move_table_out_of_p_tag(soup)
                clean_caption_tags(soup)
                make_caption_first_child(soup)

                remove_toc_backlinks(soup)
                anchor_name_to_id_and_deduplicate(soup)
                move_anchors_from_ul_to_li(soup)
                update_anchors_href(soup)
                remove_empty_p_tag(soup)

                med.data = soup.prettify()

                assert OLD_DOCTYPE in med.data, med.data[:200]

                med.data = med.data.replace(OLD_DOCTYPE, NEW_DOCTYPE)
                med.data = med.data.replace(
                    '<html>',
                    '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">')

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
        print(tag)
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




def main():
    doc = Document('book/book.html')
    doc.make_xml()
    doc.write('sicp.epub')

if __name__ == '__main__':
    main()
