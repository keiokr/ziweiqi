import argparse
import csv
import datetime
import hashlib
import os
import socket
import threading
import time
import urllib.parse
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from functools import lru_cache
from threading import Lock
import requests
from requests.adapters import HTTPAdapter
import urllib3
from bs4 import BeautifulSoup
import chardet

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')

DEBUG = False
TRYAGAIN = False

class whichAlive(object):
    def __init__(self, file, THREAD_POOL_SIZE=20, allow_redirect=False, PROXY={}):
        self.file = file
        self.filename = ''.join(file.split('/')[-1].split('.')[:-1])
        self.timenow = str(time.time()).split(".")[0]
        os.makedirs(RESULTS_DIR, exist_ok=True)
        self.outfilename = os.path.join(RESULTS_DIR, 'results2.csv')
        self.errorfilename = os.path.join(RESULTS_DIR, 'error_.txt')
        self.urllist = self.__urlfromfile()
        self.tableheader = ['no', 'url', 'ip', 'port', 'state', 'state_code', 'title', 'server', 'length', 'hash', 'other']
        self.HEADER = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
        }
        self.THREAD_POOL_SIZE = THREAD_POOL_SIZE
        self.allurlnumber = len(self.urllist)
        self.completedurl = -1
        self.allow_redirect = allow_redirect
        self.PROXY = PROXY
        self._write_lock = Lock()
        self._writer_handle = None
        self._csv_writer = None
        self._thread_local = threading.local()

    def run(self):
        tasklist = []
        start_time = datetime.datetime.now()
        need_header = not os.path.exists(self.outfilename) or os.path.getsize(self.outfilename) == 0
        with open(self.outfilename, 'a', newline='', encoding='utf-8') as f:
            self._writer_handle = f
            self._csv_writer = csv.writer(f)
            if need_header:
                self._csv_writer.writerow(self.tableheader)
            with ThreadPoolExecutor(max_workers=self.THREAD_POOL_SIZE) as t:
                for k, url in enumerate(self.urllist):
                    tasklist.append(t.submit(self.__scan, url, k + 1))
        print(f'total {self.allurlnumber}')
        if wait(tasklist, return_when=ALL_COMPLETED):
            end_time = datetime.datetime.now()
            print(f'--------------------------------\nDONE, use {(end_time - start_time).seconds} seconds')
            print(f'outfile: {self.outfilename}')

    def __scan(self, url, no, tryagainflag=False):
        def callback(no, url, ip, port, state, state_code, title, server, length, response_hash, other):
            self.completedurl += 1
            thisline = [no, url, ip, port, state, state_code, title, server, length, response_hash, other]
            nowpercent = '%.2f' % ((self.completedurl / self.allurlnumber) * 100)
            print(f'[{nowpercent}%] {url} {ip} Port-{port} {state} {title} {length} Hash-{response_hash}')
            self.__writetofile(thisline)

        ip = ''
        port = self.__get_port(url)
        state = ''
        state_code = -1
        title = ''
        server = ''
        length = -1
        response_hash = 'Hash-Error'

        try:
            if DEBUG: print(f'[+] {no} {url}')
            u = urllib.parse.urlparse(url)
            ip = self.__getwebip(u.netloc.split(':')[0])

            if self.allow_redirect:
                r = self.__get_session().get(url=url, headers=self.HEADER, timeout=15, verify=False, proxies=self.PROXY, allow_redirects=True)

                response_hash = hashlib.md5(r.content).hexdigest()
                
                titles = [self.__getwebtitle(r)]
                lengths = [str(self.__getweblength(r))]
                servers = [self.__getwebserver(r)]

                for response in r.history:
                    titles.insert(0, self.__getwebtitle(response))
                    lengths.insert(0, str(self.__getweblength(response)))
                    servers.insert(0, self.__getwebserver(response))
                
                state = 'alive'
                state_code = '->'.join([str(i.status_code) for i in r.history] + [str(r.status_code)])
                title = '->'.join(titles)
                length = '->'.join(lengths)
                server = '->'.join(servers)
            else:
                r = self.__get_session().get(url=url, headers=self.HEADER, allow_redirects=False, timeout=15, verify=False, proxies=self.PROXY)
                response_hash = hashlib.md5(r.content).hexdigest()
                state = 'alive'
                state_code = r.status_code
                title = self.__getwebtitle(r)
                length = self.__getweblength(r)
                server = self.__getwebserver(r)

            callback(no, url, ip, port, state, state_code, title, server, length, response_hash, '')

        except requests.exceptions.ConnectTimeout as e:
            if DEBUG: print(f'[ConnectTimeout] {url} {e}')
            self.__errorreport(str(e))
            state = 'dead'
            callback(no, url, ip, port, state, state_code, title, server, length, 'Hash-Error', 'ConnectTimeout')
        except requests.exceptions.ReadTimeout as e:
            if DEBUG: print(f'[ReadTimeout] {url} {e}')
            self.__errorreport(str(e))
            state = 'dead'
            callback(no, url, ip, port, state, state_code, title, server, length, 'Hash-Error', 'ReadTimeout')
        except requests.exceptions.ConnectionError as e:
            if DEBUG: print(f'[ConnectionError] {url} {e}')
            self.__errorreport(str(e))
            state = 'dead'
            callback(no, url, ip, port, state, state_code, title, server, length, 'Hash-Error', 'ConnectionError')
        except Exception as e:
            if DEBUG: print(f'[ERROR] {no} {url} {e}')
            self.__errorreport(str(e))
            if TRYAGAIN and not tryagainflag:
                self.__scan(url, no, True)
            callback(no, url, ip, port, state, state_code, title, server, length, 'Hash-Error', 'e')

    def __get_port(self, url):
        parsed_url = urllib.parse.urlparse(url)
        port = parsed_url.port
        if port is None:
            port = 80  # 默认端口为 80
        return port

    def __getwebtitle(self, response):
        try:
            # 改进编码检测，优先使用响应头中的编码信息
            if response.encoding and response.encoding.lower() != 'iso-8859-1':
                content = response.text
            else:
                # 如果响应头编码不可靠，使用chardet检测
                detected_encoding = chardet.detect(response.content)['encoding']
                if detected_encoding is None:
                    detected_encoding = 'utf-8'
                content = response.content.decode(detected_encoding, errors='replace')
            
            soup = BeautifulSoup(content, 'html.parser')
            title_tag = soup.find('title')

            if title_tag:
                return title_tag.get_text(strip=True)
            else:
                return 'No Title Found'
        except Exception as e:
            if DEBUG: print(f'[getwebtitle ERROR] {e}')
            return 'Hash-Error'

    def __getwebip(self, domain):
        return self.__cached_getwebip(domain)

    @lru_cache(maxsize=4096)
    def __cached_getwebip(self, domain):
        try:
            ip = socket.getaddrinfo(domain, 'http')
            return ip[0][4][0]
        except:
            return ''

    def __get_session(self):
        session = getattr(self._thread_local, 'session', None)
        if session is None:
            session = requests.Session()
            adapter = HTTPAdapter(pool_connections=self.THREAD_POOL_SIZE, pool_maxsize=self.THREAD_POOL_SIZE)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self._thread_local.session = session
        return session

    def __getweblength(self, response):
        try:
            return len(response.content)
        except Exception as e:
            if DEBUG: print(f'[getweblength ERROR] {e}')
            return -1

    def __getwebserver(self, response):
        try:
            # 获取多个服务器头信息
            server_headers = []
            if 'server' in response.headers:
                server_headers.append(response.headers['server'])
            if 'x-powered-by' in response.headers:
                server_headers.append(response.headers['x-powered-by'])
            
            return ' | '.join(server_headers) if server_headers else ''
        except:
            return ''

    def __urlfromfile(self):
        """读取URL文件，处理编码问题"""
        encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'iso-8859-1']
        
        for encoding in encodings_to_try:
            try:
                with open(self.file, 'r', encoding=encoding) as f:
                    lines = [i.strip() for i in f.readlines() if i.strip()]
                    print(f"成功使用 {encoding} 编码读取文件，找到 {len(lines)} 个URL")
                    return lines
            except UnicodeDecodeError:
                continue
            except Exception as e:
                if DEBUG: print(f"尝试 {encoding} 编码时出错: {e}")
                continue
        
        # 如果所有编码都失败，使用二进制模式并忽略错误
        try:
            with open(self.file, 'rb') as f:
                content = f.read()
                # 尝试自动检测编码
                detected = chardet.detect(content)
                encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
                
                try:
                    text = content.decode(encoding, errors='replace')
                except:
                    text = content.decode('utf-8', errors='replace')
                
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                print(f"使用自动检测编码 {encoding} 读取文件，找到 {len(lines)} 个URL")
                return lines
        except Exception as e:
            print(f"文件读取失败: {e}")
            return []

    def __writetofile(self, data: list):
        try:
            with self._write_lock:
                if self._writer_handle and self._csv_writer:
                    self._csv_writer.writerow(data)
                    self._writer_handle.flush()
        except Exception as e:
            print(f"写入文件错误: {e}")

    def __errorreport(self, message):
        try:
            with open(self.errorfilename, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.datetime.now()} - {message}\n")
        except Exception as e:
            print(f"写入错误日志失败: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(usage='whichAlive usage')
    parser.add_argument('-f', '--file', default='url.txt', help='URL lists file.')
    parser.add_argument('--proxy', default='', help='Set proxy, such as 127.0.0.1:8080')
    parser.add_argument('-t', '--thread', default=20, type=int, help='Set max threads, default 20')
    parser.add_argument('-d', '--debug', default=False, action='store_true', help='print some debug information')
    parser.add_argument('--try-again', default=False, action='store_true', help='If some error, try again scan that url once', dest='tryagain')
    parser.add_argument('--encoding', default='', help='Specify file encoding (utf-8, gbk, etc.)')
    args = parser.parse_args()

    DEBUG = args.debug
    TRYAGAIN = args.tryagain

    w = whichAlive(
        file=args.file,
        THREAD_POOL_SIZE=args.thread,
        allow_redirect=True,
        PROXY={'http': args.proxy, 'https': args.proxy}
    )
    w.run()
