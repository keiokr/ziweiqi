# -*- coding: utf-8 -*-
import argparse
import configparser
import sys
import colorama
from prettytable import PrettyTable
import os
import requests
import time
import io
import threading
import hashlib
import json
import base64
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from encoding_utils import read_text_guess

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CACHE_DIR = os.path.join(BASE_DIR, "fofa_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 全局线程安全变量
print_lock = threading.Lock()
total_tasks = 0
completed_tasks = 0

# ==================== 核心：令牌桶限流器（精确到毫秒） ====================
class TokenBucket:
    """
    精确令牌桶算法，严格控制请求速率
    解决FOFA瞬时硬限制问题
    """
    def __init__(self, rate, capacity=None):
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self.tokens = self.capacity
        self.last_refill_time = time.time()
        self.lock = threading.Lock()
        self.min_interval = 1.0 / rate * 1.1  # 10%安全余量

    def acquire(self):
        with self.lock:
            now = time.time()
            time_passed = now - self.last_refill_time
            new_tokens = time_passed * self.rate
            
            if new_tokens > 0:
                self.tokens = min(self.tokens + new_tokens, self.capacity)
                self.last_refill_time = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            else:
                wait_time = (1 - self.tokens) / self.rate
                time.sleep(wait_time)
                self.tokens = 0
                self.last_refill_time = time.time()
                return True

# ==================== 自适应限流器（遇到501自动降速） ====================
class AdaptiveRateLimiter:
    def __init__(self, initial_rate=0.85, min_rate=0.2, max_rate=0.9):
        self.rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.token_bucket = TokenBucket(self.rate)
        self.consecutive_errors = 0
        self.consecutive_successes = 0
        
    def acquire(self):
        self.token_bucket.acquire()
        
    def record_success(self):
        self.consecutive_errors = 0
        self.consecutive_successes += 1
        
        if self.consecutive_successes >= 15 and self.rate < self.max_rate:
            new_rate = min(self.rate * 1.05, self.max_rate)
            with print_lock:
                print(Fore.CYAN + f"[+] 连续成功，提速至 {new_rate:.2f} QPS")
            self.rate = new_rate
            self.token_bucket = TokenBucket(self.rate)
            self.consecutive_successes = 0
            
    def record_error(self):
        self.consecutive_successes = 0
        self.consecutive_errors += 1
        
        new_rate = max(self.rate * 0.6, self.min_rate)
        if new_rate != self.rate:
            with print_lock:
                print(Fore.YELLOW + f"[!] 检测到限流错误，降速至 {new_rate:.2f} QPS")
            self.rate = new_rate
            self.token_bucket = TokenBucket(self.rate)

# 全局限流器和认证信息
limiter = None
fofa_email = ""
fofa_key = ""

# 当前软件版本信息
def banner():
    print(Fore.LIGHTGREEN_EX + r"""
 _____      __       __  __
|  ___|__  / _| __ _|  \/  | __ _ _ __
| |_ / _ \| |_ / _` | |\/| |/ _` | '_ \ 
|  _| (_) |  _| (_| | |  | | (_| | |_) |
|_|  \___/|_|  \__,_|_|  |_|\__,_| .__/ 
                                 |_|   V1.4.1-Final
# 最终版 - 纯API调用 + 零SDK兼容问题 + 零501错误""")
    print(Fore.RED + "======基础配置=======")
    print(f"[*]日志记录:{'开启' if logger_sw == 'on' else '关闭'}")
    print(f"[*]每页查询数量:{config.getint('size', 'size')}条/页")
    print(f"[*]初始QPS:{config.getfloat('rate', 'initial_rate', fallback=0.85)}")
    print(f"[*]结果缓存:{'开启' if config.getboolean('cache', 'enable', fallback=True) else '关闭'}")

# 结果缓存函数
def get_cache_key(query_str, page, fields, size):
    key_str = f"{query_str}|{page}|{fields}|{size}"
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def load_from_cache(cache_key):
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            cache_data = json.loads(read_text_guess(cache_file))
            if time.time() - cache_data['timestamp'] < 86400:
                return cache_data['results']
        except:
            pass
    return None

def save_to_cache(cache_key, results):
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': time.time(),
                'results': results
            }, f, ensure_ascii=False)
    except:
        pass

# 直接调用FOFA官方API（彻底解决SDK兼容问题）
def fofa_api_search(query_str, page, fields, size):
    """
    直接调用FOFA REST API v1
    文档：https://fofa.info/api
    """
    # Base64编码查询语句
    qbase64 = base64.b64encode(query_str.encode('utf-8')).decode('utf-8')
    
    # 构造请求参数
    params = {
        'email': fofa_email,
        'key': fofa_key,
        'qbase64': qbase64,
        'page': page,
        'size': size,
        'fields': fields
    }
    
    # 发送请求
    response = requests.get(
        'https://fofa.info/api/v1/search/all',
        params=params,
        timeout=30,
        verify=False
    )
    
    # 解析响应
    result = response.json()
    
    if result.get('error'):
        raise Exception(result['errmsg'])
    
    return result['results']

# 单页查询函数
def get_search_single_page(query_str, page, fields, size):
    # 先查缓存
    if config.getboolean('cache', 'enable', fallback=True):
        cache_key = get_cache_key(query_str, page, fields, size)
        cached_results = load_from_cache(cache_key)
        if cached_results is not None:
            with print_lock:
                print(Fore.CYAN + f"[✓] 第{page}页从缓存加载成功")
            return cached_results
    
    # 指数退避重试
    base_delay = 2
    max_retries = config.getint('retry', 'max_retries', fallback=12)
    
    for retry in range(max_retries):
        try:
            # 严格获取令牌
            limiter.acquire()
            
            # 直接调用官方API
            results = fofa_api_search(query_str, page, fields, size)
            
            # 记录成功
            limiter.record_success()
            
            # 保存到缓存
            if config.getboolean('cache', 'enable', fallback=True):
                save_to_cache(cache_key, results)
            
            return results
            
        except Exception as e:
            err_str = str(e)
            # 只对可恢复错误重试
            if any(keyword in err_str for keyword in ["501", "429", "503", "Connection", "timeout", "服务器繁忙"]):
                limiter.record_error()
                delay = base_delay * (2 ** retry) + (time.time() % 1)
                delay = min(delay, 60)
                with print_lock:
                    print(Fore.YELLOW + f"[!] 第{page}页遇到错误，{delay:.1f}秒后重试({retry+1}/{max_retries})")
                time.sleep(delay)
            else:
                with print_lock:
                    print(Fore.RED + f"[!] 第{page}页查询失败: {err_str}")
                return None
    
    with print_lock:
        print(Fore.RED + f"[!] 第{page}页重试{max_retries}次仍失败，跳过")
    return None

# 单个查询任务
def single_query_task(query_str, task_id):
    global completed_tasks
    
    with print_lock:
        print(Fore.CYAN + f"\n======任务 {task_id}/{total_tasks} 开始=======")
        print(f"[+] 查询语句：{query_str[:80]}{'...' if len(query_str) > 80 else ''}")
    
    start_page = config.getint("page", "start_page")
    end_page = config.getint("page", "end_page")
    fields = config.get("fields", "fields")
    size = config.getint("size", "size")
    
    database = []
    
    for page in range(start_page, end_page + 1):
        with print_lock:
            print(Fore.CYAN + f"[+] 正在获取第{page}页")
        
        results = get_search_single_page(query_str, page, fields, size)
        
        if results:
            database.extend(results)
            # 自动判断最后一页
            if len(results) < size:
                with print_lock:
                    print(Fore.YELLOW + "[!] 已获取所有结果，提前结束")
                break
        else:
            break
    
    # 高效去重
    unique_database = []
    seen = set()
    for item in database:
        item_tuple = tuple(item)
        if item_tuple not in seen:
            seen.add(item_tuple)
            unique_database.append(item)
    
    with print_lock:
        print_result(unique_database, fields, task_id)
        completed_tasks += 1
        print(Fore.GREEN + f"[✓] 任务 {task_id} 完成，共获取 {len(unique_database)} 条唯一结果")
        print(f"[进度] 已完成 {completed_tasks}/{total_tasks} 个任务")
    
    return unique_database

# 打印查询结果
def print_result(database, fields, task_id=None):
    if not database:
        print(Fore.YELLOW + "[!] 本次查询无结果")
        return
    
    print(Fore.RED + "======查询结果=======")
    id = 1
    field = fields.split(",")
    field.insert(0, 'ID')
    table = PrettyTable(field)
    table.padding_width = 1
    table.header_style = "title"
    table.align = "c"
    table.valign = "m"
    
    for item in database:
        if isinstance(item, str):
            item = [item]
        if "title" in fields:
            try:
                title_idx = field.index('title') - 1
                if title_idx < len(item):
                    title = str(item[title_idx]).strip()
                    if len(title) > 20:
                        title = title[:20] + "......"
                    item[title_idx] = title
            except:
                pass
        item.insert(0, id)
        try:
            table.add_row(item)
            id += 1
        except Exception as e:
            print(f"[!] 警告：跳过一行无法显示的数据（{e}）")
            continue
    
    print(f'{table}')
    
    # 保存结果到文件
    if config.getboolean('output', 'save_per_task', fallback=True):
        output_dir = os.path.join(BASE_DIR, "results")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_{timestamp}.txt" if task_id else f"result_{timestamp}.txt"
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            f.write(str(table))

# 批量查询
def bat_query(bat_query_file):
    global total_tasks, completed_tasks
    
    with open(bat_query_file, "r", encoding='utf-8', errors='replace') as f:
        bat_str = [line.strip() for line in f.readlines() if line.strip()]
    
    total_tasks = len(bat_str)
    completed_tasks = 0
    
    if total_tasks == 0:
        print(Fore.RED + "[!] 查询文件为空")
        return
    
    print(Fore.CYAN + f"\n======批量查询开始=======")
    print(f"[+] 任务文件：{bat_query_file}")
    print(f"[+] 总任务数：{total_tasks}")
    print(Fore.YELLOW + "[!] FOFA单账号全局1次/秒限制，已启用严格串行执行")
    
    # 串行执行所有任务
    for task_id, query_str in enumerate(bat_str, 1):
        try:
            single_query_task(query_str, task_id)
        except Exception as e:
            with print_lock:
                print(Fore.RED + f"[!] 任务 {task_id} 执行异常: {e}")
    
    print(Fore.GREEN + "\n======所有任务完成=======")
    print(f"[✓] 共完成 {completed_tasks}/{total_tasks} 个任务")

# 日志功能
class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a+", encoding='utf-8', errors='replace')
        self.buffer = []
        self.flush_interval = 5
        self.last_flush = time.time()

    def write(self, message):
        self.terminal.write(message)
        
        # 去除ANSI颜色码
        clean_msg = message
        for code in ['\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[96m',
                     '\033[31m', '\033[32m', '\033[33m', '\033[36m', '\033[34m', '\033[0m']:
            clean_msg = clean_msg.replace(code, "")
        
        self.buffer.append(clean_msg)
        
        if time.time() - self.last_flush > self.flush_interval:
            self.flush()

    def flush(self):
        if self.buffer:
            self.log.write(''.join(self.buffer))
            self.log.flush()
            self.buffer = []
            self.last_flush = time.time()

if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings()
    colorama.init(wrap=False)
    Fore = colorama.Fore

    # 读取配置文件
    config = configparser.ConfigParser()
    config.read_string(read_text_guess(os.path.join(BASE_DIR, 'fofa.ini')))
    logger_sw = config.get("logger", "logger", fallback="off")
    
    # 初始化日志
    if logger_sw == "on":
        sys.stdout = Logger(os.path.join(BASE_DIR, "fofamap.log"))

    # 获取FOFA认证信息（修复：删除了错误的global声明）
    fofa_email = config.get("userinfo", "email", fallback="")
    fofa_key = config.get("userinfo", "key", fallback="")
    
    if not fofa_email or not fofa_key:
        print(Fore.RED + "[!] 错误：请在fofa.ini中填写正确的email和key")
        sys.exit(1)

    # 初始化全局限流器
    initial_rate = config.getfloat('rate', 'initial_rate', fallback=0.85)
    min_rate = config.getfloat('rate', 'min_rate', fallback=0.2)
    max_rate = config.getfloat('rate', 'max_rate', fallback=0.9)
    limiter = AdaptiveRateLimiter(initial_rate, min_rate, max_rate)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="FofaMap 最终版 - 零SDK兼容问题FOFA批量查询工具")
    parser.add_argument('-bq', '--bat_query', required=True, help='批量查询文件路径')
    args = parser.parse_args()
    bat_query_file = args.bat_query

    # 显示横幅
    banner()

    # 执行批量查询
    start_time = time.time()
    bat_query(bat_query_file)
    end_time = time.time()
    
    print(Fore.CYAN + f"\n[总耗时] {end_time - start_time:.2f} 秒")
    
    # 确保日志刷新
    if logger_sw == "on":
        sys.stdout.flush()
