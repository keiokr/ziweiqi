import os
import queue
import re
import subprocess
import threading
import time

from console_utils import configure_stdio, safe_print, safe_write
from encoding_utils import read_text_guess


HEARTBEAT_SECONDS = 30
# 不再设置“连续 N 秒无输出就终止”的脚本级超时；大批量资产时 fscan 可能长时间无 stdout。

configure_stdio()


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def normalize_ports_text(text):
    """把多行/逗号混合端口清洗成 fscan 可识别的逗号分隔格式，避免尾逗号。"""
    ports = []
    seen = set()
    for token in re.split(r"[\s,]+", text or ""):
        port = token.strip().strip(",")
        if not port:
            continue
        if not re.fullmatch(r"\d{1,5}(?:-\d{1,5})?", port):
            safe_print(f"跳过非法端口项: {port}")
            continue
        if port in seen:
            continue
        seen.add(port)
        ports.append(port)
    return ",".join(ports)


def run_fscan():
    """运行 fscan184.exe，使用 ip.txt 和 ports.txt；fofa端口模式保留 -pa。"""
    ip_file = r".\tools\fscan\ip.txt"
    ports_file = r".\tools\fscan\ports.txt"
    fscan_exe = os.path.abspath(r".\tools\fscan\fscan184.exe")
    output_file = r".\results\tmp\26_full_ok.txt"

    if not os.path.exists(ip_file):
        print(f"{ip_file} 文件未找到，无法执行扫描。")
        return
    if not os.path.exists(fscan_exe):
        print(f"{fscan_exe} 文件未找到，无法执行扫描。")
        return

    ports = ""
    if os.path.exists(ports_file):
        try:
            ports = normalize_ports_text(read_text_guess(ports_file))
        except Exception as e:
            print(f"读取端口文件失败: {e}")
            return

    command = [
        fscan_exe,
        "-hf",
        ip_file,
        "-np",
        "-nobr",
        "-nopoc",
        "-time", "4",
        "-t", "150",
    ]
    # fofa端口模式使用 -pa：在 fscan 默认端口基础上追加 FOFA 发现端口。
    if ports:
        command.extend(["-pa", ports])
    command.extend(["-o", output_file])

    try:
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
        if os.path.exists(output_file):
            print(f"fscan184.exe 执行完成，结果保存在 {output_file}")
        else:
            print(f"{output_file} 文件未生成。")
    except Exception as e:
        print(f"执行 fscan184.exe 时发生错误: {e}")


# 调用函数运行
run_fscan()
