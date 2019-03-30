import re
import requests
import itertools
import os
from collections import namedtuple
from lxml import etree
import logging
import sys



WebParsingResult = namedtuple('WebParsingResult', ['title', 'timestamp', 'authors', 'contents'])
PhotoMetaInfo = namedtuple('PhotoMetaInfo', ['url', 'fmt'])

def parseWeiboArticle(html):
    root = etree.HTML(html)

    def getTitle():
        return root.findtext(r".//*[@id='activity-name']").strip()

    def getTimestamp():
        ptn = re.compile(r'var publish_time = "([-0-9]+)"')
        m = ptn.search(html)
        return m.group(1) if m is not None else None

    def getAuthors():
        # return list(map(lambda n: etree.tostring(n), root.xpath(r'//div[@id="meta_content"]/span')))
        pass

    paragraphs = root.xpath(r'//div[@id="js_content"]/p')
    contents = []
    photos = []

    for p in paragraphs:
        txt = str(p.xpath("string()").strip())
        # Exit if reach the end
        if len(txt) < 20 and '赞助商' in txt:
            break;

        if txt:
            contents.append(txt)

        contents += map(lambda n: PhotoMetaInfo(url = n.get('data-src'), fmt = n.get('data-type')),
                        p.xpath(r'.//img'))

    return WebParsingResult(
        title = getTitle(),
        timestamp = getTimestamp(),
        authors = getAuthors(),
        contents = contents)




class PostCreator(object):

    def __init__(self, postPath, photoPath):
        self.postPath = postPath
        self.photoPath = photoPath


    def storePhoto(self, photoInfo, postName, photoNum):
        fname = os.path.join(self.photoPath, '{}-{}.{}'.format(postName, photoNum, photoInfo.fmt))
        try:
            resp = requests.get(photoInfo.url).content
            with open(fname, 'wb+') as f:
                f.write(resp)
            logging.info('stored photo "{}" in "{}".'.format(photoInfo.url, fname))
        except Exception as err:
            logging.error('failed to download photo "{}": {}.'.format(photoInfo.url,  str(err)))


    def create(self, id, title, timestamp, contents):
        postName = '{}-{}'.format(timestamp, id)
        photoNum = 0

        # create header
        post = ('---\n'
                'title: {}\n'
                'date: {}\n'
                'categories: 比赛\n'
                'postname: {}\n'
                '---\n\n').format(title, timestamp, postName)

        # create body
        def handleContent(cnt):
            if isinstance(cnt, PhotoMetaInfo):
                nonlocal photoNum
                photoNum += 1
                self.storePhoto(cnt, postName, photoNum)
                return '![image]( {{{{ site.post_imgpath | relative_url }}}}/{{{{ page.postname }}}}-{}.{} )'.format(photoNum, cnt.fmt)
            else:
                return str(cnt)

        post += "\n\n".join(map(handleContent, contents))

        fname = os.path.join(self.postPath, '{}-{}.md'.format(timestamp, id))
        try:
            with open(fname, 'w+') as f:
                f.write(post)
            logging.info('created post "{}".'.format(fname))
        except Exception as err:
            logging.error('failed to create post "{}": {}'.format(fname, str(err)))



if __name__ == '__main__':
    usage = '''Usage:
    python3 {} url1 [url2 ...]
    '''.format(sys.argv[0])

    if (len(sys.argv) < 2):
        print(usage)
        sys.exit()

    logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5.5s]  %(message)s",
    handlers=[
        # logging.FileHandler("{0}/{1}.log".format(logPath, fileName)),
        logging.StreamHandler()
    ])

    basePath = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
    postPath = os.path.join(basePath, '_posts')
    photoPath = os.path.join(basePath, 'assets', 'images', 'posts')

    ctor = PostCreator(postPath, photoPath)

    for url in sys.argv[1:]:
        logging.info('processing url: {}'.format(url))

        req = requests.get(url)
        req.raise_for_status()

        article =  parseWeiboArticle(req.text)
        postID = list(filter(None, url.split("/")))[-1]

        ctor.create(postID,
                    article.title,
                    article.timestamp,
                    article.contents)


