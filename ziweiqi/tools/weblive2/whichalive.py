import argparse
import csv
import os
import sys
import threading
import time
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from threading import Lock
from requests.adapters import HTTPAdapter
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from encoding_utils import read_lines_guess

RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')

class DomainChecker:
    def __init__(self, file, THREAD_POOL_SIZE=20, PROXY={}):
        self.file = file
        os.makedirs(RESULTS_DIR, exist_ok=True)
        self.outfilename = os.path.join(RESULTS_DIR, 'output.csv')
        self.urllist = self.__urlfromfile()
        self.HEADER = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
        }
        self.THREAD_POOL_SIZE = THREAD_POOL_SIZE
        self.allurlnumber = len(self.urllist)
        self.PROXY = PROXY
        self._write_lock = Lock()
        self._writer_handle = None
        self._csv_writer = None
        self._thread_local = threading.local()

    def run(self):
        """运行检查"""
        tasklist = []
        start_time = time.time()
        need_header = not os.path.exists(self.outfilename) or os.path.getsize(self.outfilename) == 0
        with open(self.outfilename, 'a', newline='', encoding='utf-8') as f:
            self._writer_handle = f
            self._csv_writer = csv.writer(f)
            if need_header:
                self._csv_writer.writerow(['url', 'state_code'])
            with ThreadPoolExecutor(max_workers=self.THREAD_POOL_SIZE) as executor:
                for k, url in enumerate(self.urllist):
                    tasklist.append(executor.submit(self.__scan, url, k + 1))

                wait(tasklist, return_when=ALL_COMPLETED)
        end_time = time.time()
        print(f'检查完成，耗时 {end_time - start_time:.2f} 秒')
        print(f'输出文件：{self.outfilename}')

    def __scan(self, url, no):
        """扫描单个 URL"""
        def callback(no, url, state_code):
            """将有效的结果写入文件"""
            if state_code != 'Failed':  # 过滤掉 'Failed' 的行
                thisline = [url, state_code]
                print(f'写入结果: {thisline}')
                self.__writetofile(thisline)

        # 尝试 http 和 https 协议
        for protocol in ['http', 'https']:
            full_url = f'{protocol}://{url}'
            try:
                # 设置超时为5秒
                response = self.__get_session().get(full_url, headers=self.HEADER, timeout=5, verify=False, proxies=self.PROXY)
                state_code = response.status_code
                print(f'{full_url} 返回状态码: {state_code}')
                callback(no, full_url, state_code)
            except requests.exceptions.RequestException as e:
                # 如果连接失败，无论是超时还是其他问题，仍然记录状态
                print(f'{full_url} 连接失败: {e}')
                callback(no, full_url, 'Failed')

    def __urlfromfile(self):
        """从文件读取 URL"""
        return [i.strip() for i in read_lines_guess(self.file)]

    def __get_session(self):
        session = getattr(self._thread_local, 'session', None)
        if session is None:
            session = requests.Session()
            adapter = HTTPAdapter(pool_connections=self.THREAD_POOL_SIZE, pool_maxsize=self.THREAD_POOL_SIZE)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self._thread_local.session = session
        return session

    def __writetofile(self, data: list):
        """写入 CSV 文件"""
        try:
            with self._write_lock:
                if self._writer_handle and self._csv_writer:
                    if self._writer_handle.tell() == 0:
                        self._csv_writer.writerow(['url', 'state_code'])
                    self._csv_writer.writerow(data)
                    self._writer_handle.flush()
            print(f'数据已写入: {data}')
        except Exception as e:
            print(f'写入文件时发生错误: {e}')

if __name__ == '__main__':
    # 命令行参数解析
    parser = argparse.ArgumentParser(usage='DomainChecker usage')
    parser.add_argument('-f', '--file', default='domains.txt', help='URL lists file.')
    parser.add_argument('--proxy', default='', help='Set proxy, such as 127.0.0.1:8080')
    parser.add_argument('-t', '--thread', default=30, type=int, help='Set max threads, default 30')
    args = parser.parse_args()

    # 设置代理
    PROXY = {'http': args.proxy, 'https': args.proxy} if args.proxy else {}

    # 执行检查
    checker = DomainChecker(
        file=args.file,
        THREAD_POOL_SIZE=args.thread,
        PROXY=PROXY
    )
    checker.run()
