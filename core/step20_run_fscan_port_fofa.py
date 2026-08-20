import os
import queue
import re
import subprocess
import threading
import time

from console_utils import configure_stdio, safe_print, safe_write
from encoding_utils import read_text_guess
from fscan_utils import make_run_log_path, read_normalized_ports, rewrite_ipv4_file


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
    """运行 fscan184.exe，使用公网平衡参数扫描 fscan/ip.txt 和 FOFA 相关端口。"""
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

    ip_count, invalid_ips, duplicate_ips = rewrite_ipv4_file(ip_file)
    safe_print(f"fscan 最终 IP 校验完成: 有效 {ip_count}，去重 {duplicate_ips}，非法 {len(invalid_ips)}")
    if invalid_ips:
        safe_print(f"已跳过非法 IP 示例: {', '.join(invalid_ips[:10])}")
    if ip_count == 0:
        print("fscan 最终 IP 为空，跳过扫描。")
        return

    ports = ""
    if os.path.exists(ports_file):
        try:
            valid_ports, invalid_ports, duplicate_ports = read_normalized_ports(ports_file)
            ports = ",".join(valid_ports)
            safe_print(
                f"fscan 最终端口校验完成: 有效 {len(valid_ports)}，"
                f"去重 {duplicate_ports}，非法 {len(invalid_ports)}"
            )
            if invalid_ports:
                safe_print(f"已跳过非法端口示例: {', '.join(invalid_ports[:10])}")
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
        "-time", "3",
        "-t", "200",
    ]
    # FOFA 端口模式仍保留 -pa：在 fscan 默认端口基础上追加 FOFA 发现端口。
    if ports:
        command.extend(["-pa", ports])
    command.extend(["-o", output_file])

    try:
        print(f"执行命令: {' '.join(command)}")
        run_log = make_run_log_path("fscan_fofa")
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
        if os.path.exists(output_file):
            print(f"fscan184.exe 执行完成，结果保存在 {output_file}")
        else:
            print(f"{output_file} 文件未生成。")
    except Exception as e:
        print(f"执行 fscan184.exe 时发生错误: {e}")


# 调用函数运行
run_fscan()
