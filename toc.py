from collections import namedtuple
from itertools import count
from media import Medium

FlatTocInfo = namedtuple('FlatTocInfo', 'href, text, level')
HierarchicalTocInfo = namedtuple('HierarchicalTocInfo', 'href, text, level, parent, children')

class Toc:
    def __init__(self):
        self.entries = []

    def add(self, entry):
        self.entries.append(entry)

    def hierarchical_toc_entries(self):
        root = HierarchicalTocInfo(None, None, 0, None, [])
        previous = root

        for item in self.entries:
            if item.level == 1 + previous.level:
                parent = previous
            elif item.level > 1 + previous.level:
                raise ValueError('TOC entries can not skip levels')
            else:
                while item.level < previous.level:
                    previous = previous.parent
                parent = previous.parent
            new_item = HierarchicalTocInfo(item.href, item.text, item.level, parent, [])
            parent.children.append(new_item)
            previous = new_item
        return root.children

    def ncx(self, doc):
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="eng">',
            '  <head>',
           f'    <meta content="urn:uuid:{doc.book_uuid}" name="dtb:uid"/>',
            '    <meta content="3" name="dtb:depth"/>',
            '    <meta content="0" name="dtb:totalPageCount"/>',
            '    <meta content="0" name="dtb:maxPageNumber"/>',
            '  </head>',
           f'  <docTitle><text>{doc.title}</text></docTitle>',
            '  <navMap>',
        ]

        num = count(1)
        def handle(entries):
            for item in entries:
                ind = '      ' + '    '*item.level
                n = next(num)
                lines.append(f'{ind}<navPoint id="num_{n}" playOrder="{n}">')
                lines.append(f'{ind}  <navLabel><text>{item.text}</text></navLabel>')
                lines.append(f'{ind}  <content src="{item.href}"/>')
                if item.children:
                    handle(item.children)
                lines.append(f'{ind}</navPoint>')
        handle(self.hierarchical_toc_entries())

        lines.append('  </navMap>')
        lines.append('</ncx>')

        return Medium(name='toc.ncx',
                      data='\n'.join(lines),
                      id='toc',
                      attributes={'media-type': 'application/x-dtbncx+xml'})

    def xhtml(self, doc):
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">',
            '  <head>',
           f'    <title>{doc.title}</title>',
            '  </head>',
            '  <body>',
            '    <nav epub:type="toc">',
            '      <ol>',
        ]

        def handle(entries):
            for item in entries:
                ind = '      ' + '    '*item.level
                lines.append(f'{ind}<li>')
                lines.append(f'{ind}  <a href="{item.href}">{item.text}</a>')
                if item.children:
                    lines.append(f'{ind}  <ol>')
                    handle(item.children)
                    lines.append(f'{ind}  </ol>')
                lines.append(f'{ind}</li>')
        handle(self.hierarchical_toc_entries())

        lines.append('      </ol>')
        lines.append('    </nav>')
        lines.append('  </body>')
        lines.append('</html>')

        return Medium(name='toc.xhtml',
                      data='\n'.join(lines),
                      id='nav',
                      attributes={'properties': 'nav'})
