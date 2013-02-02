# encoding: utf-8

import re
import os
import sys

import requests
from bs4 import BeautifulSoup


class TextNotFoundException(Exception):
    pass


def file_type_from_url(url):
    return re.search(r'/st/([^/]+)/', url).group(1)


def get_soup(url):
    r = requests.get(url)
    return BeautifulSoup(r.text)


def get_soup_from_flvcd(relative):
    # encoding of site flvcd is gb18030
    domain = 'http://www.flvcd.com/'
    url = domain + relative
    r = requests.get(url)
    r.encoding = 'gb18030'
    soup = BeautifulSoup(r.text, from_encoding='gb18030')
    return soup


def follow_link(soup, text):
    text_tag = soup.body.find(text=text)
    if text_tag is None:
        raise TextNotFoundException
    a = text_tag.find_parent('a')
    return get_soup_from_flvcd(a['href'])


def get_download_link_and_name(url):
    soup = get_soup_from_flvcd('parse.php?kw=' + url)
    # find better version of video
    for text in [u'粤语版', u'高清版解析', u'超清版解析']:
        try:
            soup = follow_link(soup, text)
        except TextNotFoundException:
            pass

    name_tag = soup.body.find('strong', text=u'当前解析视频：').next_sibling
    name = name_tag.string.strip(u'" \t\n\r')
#    print name

    # they store the links in the get_m3u form
    download_tag = soup.body.find('form', action='get_m3u.php')
    urls = download_tag.input['value'].split()

    ext = file_type_from_url(urls[0])

    res = []
    for i, url in enumerate(urls):
        filename = u'{}-{:0>2}.{}'.format(name, i, ext)
        res.append((url, filename))
    return res


def youku_download_playlist(url, output_dir='.', start_episode=1):
    assert re.match(r'http://www.youku.com/show_page/id_\w+\.html', url)
    output_dir = os.path.expanduser(output_dir)

    urls = get_urls_from_show_page(url)
    stop_episode = len(urls)
    if start_episode > len(urls):
        print u'No new episode found, skipping...'
    else:
        urls = urls[start_episode - 1:]
        for url in urls:
            youku_download(url, output_dir)
    return stop_episode


def youku_download(url, output_dir='.'):
    urls_names = get_download_link_and_name(url)
    for url, filename in urls_names:
        save_file(url, filename, output_dir)


def get_urls_from_show_page(url):
    soup = get_soup(url)
    episode = soup.find(id="episode").contents[0]
    urls = []
    for a in episode.find_all('a'):
        urls.append(a['href'])
    return urls


def save_file(url, filename, output_dir):
    r = requests.get(url, stream=True)
    file_size = int(r.headers['content-length'])
    block_size = 1024 * 256
    filepath = os.path.join(output_dir, filename)
    bar = ProgressBar(file_size, filename)

    if os.path.exists(filepath):
        if os.path.getsize(filepath) == file_size:
            bar.done()
            print u'Skip {}: file already exists'.format(filename)
            return
        else:
            bar.done()
            print u'Overwriting {} ...'.format(filename)

    with open(filepath, 'wb') as output:
        received = 0
        while True:
            buffer = r.raw.read(block_size)
            if not buffer:
                break
            received += len(buffer)
            output.write(buffer)
            bar.update_received(len(buffer))
    assert received == file_size == os.path.getsize(filepath)
    bar.done()


class ProgressBar:
    def __init__(self, total_size, filename):
        self.displayed = False
        self.total_size = total_size
        self.filename = filename
        self.received = 0

    def update(self):
        self.displayed = True
        bar_size = 50
        percent = self.received * 100.0 / self.total_size
        if percent > 100: percent = 100.0
        done = int(bar_size * percent / 100.0)
        working = bar_size * percent / 100.0 - done
        if working > 0.8:
            plus = u'='
        elif working > 0.4:
            plus = u'+'
        else:
            plus = u'-'
        bar = u'=' * done + plus
        out = u'Downloading {}: [{:<50}] {:>3.0f}%'.format(self.filename,
                                                           bar, percent)
        sys.stdout.write(u'\r' + out)
        sys.stdout.flush()

    def update_received(self, n):
        self.received += n
        self.update()

    def done(self):
        if self.displayed:
            print
            self.displayed = False


def main():
    conf = 'youku.conf'
    # the conf file describe task as: url output_dir start_episode
    with open(conf, 'r') as conf_file, \
            open(conf + '.tmp', 'w') as tmp_file:
        for line in conf_file:
            if line.startswith('#'):
                mod_line = line
            else:
                info = line.strip().split()
                stop_episode = youku_download_playlist(info[0], info[1],
                                                       int(info[2]))
#                stop_episode = 25
                mod_info = info[:2] + [str(stop_episode + 1)] + info[3:]
                mod_line = ' '.join(mod_info)
            tmp_file.write(mod_line)

    os.remove(conf)
    os.rename(conf + '.tmp', conf)


if __name__ == "__main__":
#    url = 'http://www.youku.com/show_page/id_z6283e0ea27c011e2b16f.html'
#    youku_download_playlist(url, start_episode=22)
    main()
