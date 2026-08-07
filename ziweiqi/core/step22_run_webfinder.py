import subprocess
import os
import shutil
import time
import queue
import threading
import sys
import re
from console_utils import configure_stdio, safe_print, safe_write

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
HEARTBEAT_SECONDS = 30
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

configure_stdio()


def clean_asset_line(line):
    """清洗大批量资产中的控制字符、emoji 前缀和重复空白，保留 URL 主体。"""
    text = _CONTROL_CHARS_RE.sub("", str(line or "")).strip()
    if not text:
        return ""

    # 常见输入可能是 "1,http://a.com"、"http://a.com xxx" 或带状态符号前缀。
    match = re.search(r"(https?://[^\s,;\"'<>]+)", text, re.I)
    if match:
        return match.group(1).rstrip("/ \t\r\n")
    return text

def copy_url_file():
    src_file = os.path.join(PROJECT_ROOT, "results", "tmp", "23_ziyumingcore_2.txt")
    dest_file = os.path.join(PROJECT_ROOT, "tools", "weblive2", "url.txt")
    
    try:
        seen = set()
        cleaned = []
        with open(src_file, "r", encoding="utf-8", errors="replace") as src:
            for raw_line in src:
                line = clean_asset_line(raw_line)
                if not line or line in seen:
                    continue
                seen.add(line)
                cleaned.append(line)

        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        with open(dest_file, "w", encoding="utf-8", newline="\n") as dst:
            if cleaned:
                dst.write("\n".join(cleaned) + "\n")

        safe_print(f"文件已成功清洗并复制到 {dest_file}，原始去噪后保留 {len(cleaned)} 条")
    except FileNotFoundError:
        safe_print(f"Error: 源文件 {src_file} 未找到。")
    except Exception as e:
        safe_print(f"Error during file copy: {e}")

def run_weblive_script():
    script_path = os.path.join(PROJECT_ROOT, "tools", "weblive2", "whichalive.py")
    
    url_file = os.path.join(PROJECT_ROOT, "tools", "weblive2", "url.txt")
    if not os.path.exists(url_file):
        print(f"Error: {url_file} does not exist.")
        return
    
    # 设置命令
    command = [sys.executable, script_path, "-f", url_file, "-t", "30" ]
    
    try:
        # 不能 capture_output 后长时间静默，否则外层“无输出 watchdog”会误判为卡死。
        safe_print(f"此处请耐心等待或者查看 {os.path.join(PROJECT_ROOT, 'results', 'output.csv')} 文件大小变化")
        safe_print(f"{' '.join(command)}")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8:replace"
        env["PYTHONUTF8"] = "1"

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT,
            env=env,
        )

        output_queue = queue.Queue()

        def reader():
            try:
                for line in process.stdout:
                    output_queue.put(line)
            finally:
                output_queue.put(None)

        threading.Thread(target=reader, daemon=True).start()

        started_at = time.monotonic()
        last_output_at = started_at
        last_heartbeat_at = started_at
        reader_done = False

        while True:
            drained = False
            while True:
                try:
                    item = output_queue.get_nowait()
                except queue.Empty:
                    break
                drained = True
                if item is None:
                    reader_done = True
                    continue
                last_output_at = time.monotonic()
                safe_write(item)

            now = time.monotonic()
            if now - last_heartbeat_at >= HEARTBEAT_SECONDS:
                elapsed = int(now - started_at)
                idle = int(now - last_output_at)
                size = 0
                output_csv = os.path.join(PROJECT_ROOT, "results", "output.csv")
                if os.path.exists(output_csv):
                    try:
                        size = os.path.getsize(output_csv)
                    except OSError:
                        size = 0
                safe_print(
                    f"[HEARTBEAT] weblive2 执行中 | 已运行 {elapsed}s | 空闲 {idle}s | output.csv={size} bytes",
                    flush=True,
                )
                last_heartbeat_at = now

            if process.poll() is not None and reader_done and output_queue.empty():
                break

            if not drained:
                time.sleep(0.5)

        return_code = process.wait()
        if return_code != 0:
            safe_print(f"Error during execution: whichalive.py exit={return_code}")

    except Exception as e:
        safe_print(f"Error during execution: {e}")

if __name__ == "__main__":
    # 先复制文件
    copy_url_file()

    # 运行 weblive 脚本
    run_weblive_script()
