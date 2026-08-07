import os
import subprocess
import sys
import time
import queue
import threading
from console_utils import configure_stdio, safe_print, safe_write

HEARTBEAT_SECONDS = 30
# 不再设置“连续 N 秒无输出就终止”的脚本级超时；大批量全端口扫描可能长时间无 stdout。

configure_stdio()


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def run_fscan(fscan_exe, ip_file, output_file):
    """
    调用 fscan184.exe 进行扫描，将结果追加写入 output_file。
    """
    try:
        command = [
            fscan_exe,
            "-hf", ip_file,
            "-np",
            "-p", "1-65535",
            "-nobr",
            "-nopoc",
            "-time", "4",
            "-t", "150",
            "-o", output_file,
        ]
        print(f"执行命令: {' '.join(command)}")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
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
                idle = int(now - last_output_at)
                elapsed = int(now - started_at)
                safe_print(f"[HEARTBEAT] fscan 执行中 | 已运行 {elapsed}s | 空闲 {idle}s", flush=True)
                last_heartbeat_at = now

            if process.poll() is not None and reader_done and output_queue.empty():
                break

            if not drained:
                time.sleep(0.5)

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"fscan 返回了非 0 退出码：{return_code}")
    except Exception as e:
        print(f"执行 fscan 命令失败: {e}")

def main():
    # 文件路径
    fscan_exe = '.\\tools\\fscan\\fscan184.exe'
    ip_file = '.\\tools\\fscan\\ip.txt'
    output_file = '.\\results\\tmp\\26_full_ok.txt'

    # 检查必要文件是否存在
    for file in [fscan_exe, ip_file]:
        if not os.path.exists(file):
            print(f"文件 {file} 不存在，退出。")
            return

    # 调用 fscan 进行扫描
    run_fscan(fscan_exe, ip_file, output_file)

    print(f"扫描完成，结果已追加到 {output_file}")

# 运行脚本
if __name__ == "__main__":
    main()
