import os
import subprocess
import sys
import time
import queue
import threading
from console_utils import configure_stdio, safe_print, safe_write
from fscan_utils import make_run_log_path, rewrite_ipv4_file

HEARTBEAT_SECONDS = 30
# 不设置“连续 N 秒无输出就终止”的脚本级超时；公网全端口扫描遇到防火墙时可能长时间无 stdout。

configure_stdio()


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def run_fscan(fscan_exe, ip_file, output_file):
    """
    调用 fscan184.exe 进行公网全端口扫描，结果写入 output_file，过程输出写入 results/tmp 日志。
    """
    try:
        command = [
            fscan_exe,
            "-hf", ip_file,
            "-np",
            "-p", "1-65535",
            "-nobr",
            "-nopoc",
            "-time", "3",
            "-t", "200",
            "-o", output_file,
        ]
        print(f"执行命令: {' '.join(command)}")
        run_log = make_run_log_path("fscan_all")
        print(f"fscan 过程输出写入日志: {run_log}")

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
            line_count = 0
            try:
                with open(run_log, "a", encoding="utf-8", errors="replace") as log_file:
                    for line in process.stdout:
                        log_file.write(line)
                        line_count += 1
                        if line_count % 100 == 0:
                            log_file.flush()
                            output_queue.put(("progress", line_count))
            finally:
                output_queue.put(("done", line_count))

        threading.Thread(target=reader, daemon=True).start()

        started_at = time.monotonic()
        last_heartbeat_at = started_at
        reader_done = False
        logged_lines = 0

        while True:
            drained = False
            while True:
                try:
                    item = output_queue.get_nowait()
                except queue.Empty:
                    break
                drained = True
                kind, value = item
                if kind == "done":
                    reader_done = True
                    logged_lines = value
                    continue
                if kind == "progress":
                    logged_lines = value

            now = time.monotonic()
            if now - last_heartbeat_at >= HEARTBEAT_SECONDS:
                elapsed = int(now - started_at)
                safe_print(
                    f"[HEARTBEAT] fscan 执行中 | 已运行 {elapsed}s | "
                    f"过程输出 {logged_lines} 行 | 日志 {run_log}",
                    flush=True,
                )
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

    ip_count, invalid_ips, duplicate_ips = rewrite_ipv4_file(ip_file)
    print(f"fscan 最终 IP 校验完成: 有效 {ip_count}，去重 {duplicate_ips}，非法 {len(invalid_ips)}")
    if invalid_ips:
        print(f"已跳过非法 IP 示例: {', '.join(invalid_ips[:10])}")
    if ip_count == 0:
        print("fscan 最终 IP 为空，跳过扫描。")
        return

    # 调用 fscan 进行扫描
    run_fscan(fscan_exe, ip_file, output_file)

    print(f"扫描完成，结果已追加到 {output_file}")

# 运行脚本
if __name__ == "__main__":
    main()
