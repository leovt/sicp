'''
This script downloads the full text and saves it locally.
referenced stylesheets and images are also downloaded.

Care is taken to avoid more than 1 request/second and
to avoid downloading files which are already available locally.

local directory './book' needs to exist, it is not created automatically on purpose.
'''

import urllib.request
import time
import os
from html.parser import HTMLParser
from urllib.parse import urljoin

BASE_URL = 'https://mitpress.mit.edu/sites/default/files/sicp/full-text/'
START_URL = BASE_URL + 'book/book.html'

def to_local(url):
    '''return the local relative name for the remote url'''
    if url.startswith(BASE_URL):
        return url[len(BASE_URL):]
    else:
        return None

def download(url, name):
    '''download the resource at url and save it under the given local name

        if a local file already exists do nothing.
    '''
    if os.path.exists(name):
        #print(name, 'is already downloaded')
        return
    time.sleep(1.0)
    page = urllib.request.urlopen(url)
    with open(name, 'wb') as local:
        local.write(page.read())

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

def process(url):
    ''' download the resource at url and follow links as given by the
        FindChildren class
    '''
    name = to_local(url)
    if name is None:
        print('not processing', url)
        return
    print('processing', url)
    download(url, name)
    parser = FindChildren()
    parser.feed(open(name).read())
    for ref in parser.download_only:
        absref = urljoin(url, ref)
        #print(' ->', absref)
        local = to_local(absref)
        if local is None:
            print('not downloading', ref, absref)
        else:
            download(absref, local)
    if len(parser.follow) > 1:
        print('Multiple successors found')
    for ref in parser.follow:
        absref = urljoin(url, ref)
        #print(' ->>', absref)
        process(absref)

if __name__ == '__main__':
    process(START_URL)
