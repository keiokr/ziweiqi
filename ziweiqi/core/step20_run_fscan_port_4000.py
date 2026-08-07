import os
import subprocess
import sys
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from console_utils import configure_stdio, safe_print, safe_write

HEARTBEAT_SECONDS = 30
# 不再设置“连续 N 秒无输出就终止”的脚本级超时；大批量资产时 fscan 可能长时间
# 只写结果文件或处于探测阶段，不能因为空闲时间较长直接杀进程。
BATCH_SIZE = 300
MAX_PARALLEL_BATCHES = 1

configure_stdio()


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def split_ports_file(ports_file, batch_size=BATCH_SIZE):
    """
    将 ports_4000.txt 分割为多个子文件，每个子文件包含 batch_size 行端口。
    文件命名为 ports_4000_1.txt, ports_4000_2.txt 等。
    """
    try:
        # 读取原始端口文件
        with open(ports_file, 'r', encoding='utf-8', errors='replace') as f:
            ports = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"读取端口文件失败: {e}")
        return []

    # 分割文件
    output_files = []
    for i in range(0, len(ports), batch_size):
        batch = ports[i:i + batch_size]
        output_file = ports_file.replace('.txt', f'_{len(output_files) + 1}.txt')

        try:
            # 写入每个子文件
            with open(output_file, 'w', encoding='utf-8', errors='replace') as f:
                f.write('\n'.join(batch) + '\n')
            output_files.append(output_file)
            print(f"生成文件: {output_file}，包含 {len(batch)} 行端口")
        except Exception as e:
            print(f"写入子文件失败: {e}")

    print(f"共生成 {len(output_files)} 个子文件。")
    return output_files


def run_fscan(fscan_exe, ip_file, ports_file, output_file):
    """
    调用 fscan184.exe 进行扫描，将结果追加写入 output_file。
    """
    try:
        # 读取端口文件并整合到一行
        with open(ports_file, 'r', encoding='utf-8', errors='replace') as f:
            ports = [line.strip() for line in f if line.strip()]
        ports_str = ','.join(ports).strip(',')
    except Exception as e:
        print(f"读取或处理端口文件失败: {e}")
        return

    command = [
        fscan_exe,
        "-hf", ip_file,
        "-np",
        "-p", ports_str,
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


def merge_result_files(result_files, final_output_file):
    merged = []
    seen = set()
    for file_path in result_files:
        if not os.path.exists(file_path):
            continue
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                text = line.strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                merged.append(text)

    with open(final_output_file, "w", encoding="utf-8") as f:
        if merged:
            f.write("\n".join(merged) + "\n")


def run_batched_fscan_parallel(fscan_exe, ip_file, temp_files, final_output_file):
    temp_outputs = []
    errors = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BATCHES) as executor:
        futures = {}
        for index, temp_file in enumerate(temp_files, start=1):
            batch_output = f"{final_output_file}.{index}.tmp"
            temp_outputs.append(batch_output)
            if os.path.exists(batch_output):
                try:
                    os.remove(batch_output)
                except OSError as exc:
                    print(f"清理旧 fscan 临时结果失败: {batch_output} -> {exc}")
            futures[executor.submit(run_fscan, fscan_exe, ip_file, temp_file, batch_output)] = batch_output

        for future in as_completed(futures):
            batch_output = futures[future]
            try:
                future.result()
            except Exception as exc:
                errors.append((batch_output, exc))
                print(f"分批 fscan 失败但会保留并合并已有结果: {batch_output} -> {exc}")

    # 不管是否有分批失败，都先合并已经落盘的分批结果，避免大批量扫描中途异常导致结果丢失。
    merge_result_files(temp_outputs, final_output_file)

    # 全部分批成功时清理 tmp；存在失败时保留 tmp，方便 step21 兜底提取和人工排查。
    if not errors:
        for path in temp_outputs:
            try:
                os.remove(path)
            except Exception:
                pass
    else:
        raise RuntimeError(f"fscan 分批扫描存在 {len(errors)} 个失败批次，已合并现有结果并保留 tmp 文件。")


def clean_temp_files(file_list):
    """
    删除临时生成的子文件。
    """
    for file in file_list:
        try:
            os.remove(file)
            print(f"已删除临时文件: {file}")
        except Exception as e:
            print(f"删除文件 {file} 失败: {e}")




def main():
    # 文件路径
    ports_file = '.\\tools\\fscan\\ports_4000.txt'
    fscan_exe = '.\\tools\\fscan\\fscan184.exe'
    ip_file = '.\\tools\\fscan\\ip.txt'
    output_file = '.\\results\\tmp\\26_full_ok.txt'


    # 检查必要文件是否存在
    for file in [ports_file, fscan_exe, ip_file]:
        if not os.path.exists(file):
            print(f"文件 {file} 不存在，退出。")
            return

    # 分割端口文件
    temp_files = split_ports_file(ports_file, batch_size=500)
    if not temp_files:
        print("未生成临时文件，退出。")
        return

    # 批量并发调用 fscan，单批写独立临时结果，最后统一合并
    run_batched_fscan_parallel(fscan_exe, ip_file, temp_files, output_file)

    # 删除临时文件
    clean_temp_files(temp_files)
    print(f"扫描完成，结果已追加到 {output_file}")



# 运行脚本
if __name__ == "__main__":
    main()
