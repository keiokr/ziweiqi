# -*- coding: utf-8 -*-
import math
import os
import re
import shutil
import subprocess
import sys
import time
import statistics
from encoding_utils import read_lines_guess


SOURCE_FILE = r".\results\tmp\7_domains.txt"
KDOMAIN_FILE = r".\tools\ksubdomain\domains.txt"
TEST_OUTPUT_FILE = r".\results\tmp\ksubdomainfindb.txt"
OUTPUT_FILE = r".\tools\ksubdomain\ksubok.txt"
FIRST_DICT = r".\tools\ksubdomain\300.txt"
SECOND_DICT = r".\tools\ksubdomain\20W.txt"


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

# ========== 可配置参数 ==========
TEST_SECONDS = 3                       # 测速运行秒数
BANDWIDTH_USAGE = 1.0                  # 带宽使用比例
DEFAULT_BANDWIDTH_MBPS = 1             # 找不到 pps 时的后备带宽
CALIBRATION_PPS = 26496.0              # 2G8H / 8M 环境下的实测基准 pps
CALIBRATION_BANDWIDTH_MBPS = 8.0       # 对应的基准带宽（Mbps）
# =================================


def copy_domains():
    source_file = SOURCE_FILE
    destinations = [
        r".\tools\OneForAll\domains.txt",
        r".\tools\subfinder\domains.txt",
        KDOMAIN_FILE,
    ]

    for destination in destinations:
        try:
            shutil.copy(source_file, destination)
            print(f"已将 {source_file} 复制到 {destination}")
            if os.path.exists(destination):
                print(f"文件成功复制到: {destination}")
            else:
                print(f"文件复制失败到: {destination}")
        except FileNotFoundError as exc:
            print(f"文件 {source_file} 未找到: {exc}")
        except Exception as exc:
            print(f"复制文件时出错: {exc}")


def run_ksubdomain_test():
    command = [r".\tools\ksubdomain\ksubdomain.exe", "-test"]
    output_file = TEST_OUTPUT_FILE

    try:
        with open(output_file, "w", encoding="utf-8") as handle:
            process = subprocess.Popen(
                command,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=child_env(),
            )
            time.sleep(TEST_SECONDS)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        print(f"ksubdomain.exe 输出已保存到 {output_file}")
    except Exception as exc:
        print(f"运行 ksubdomain 测速时出错: {exc}")


def calculate_bandwidth_from_file(file_path):
    """
    从 test 输出文件读取 pps，取中位数后按基准比例计算实际带宽上限，
    再返回可用于 -b 的整数 Mbps。
    """
    try:
        lines = read_lines_guess(file_path)

        pps_values = []
        for line in lines:
            # 匹配类似 "平均每秒速度:29347pps" 的字段
            match = re.search(r"[:：]\s*(\d+)\s*pps", line, re.IGNORECASE)
            if match:
                pps_values.append(int(match.group(1)))

        if not pps_values:
            print("没有找到有效的 pps 数据，使用默认带宽 1 Mbps。")
            return DEFAULT_BANDWIDTH_MBPS

        pps_value = statistics.median(pps_values)
        print(f"测速得到的 pps 中位数: {pps_value:.0f} pps")

        # 根据当前机器的实测基准比例推算实际带宽
        estimated_bandwidth_mbps = (pps_value / CALIBRATION_PPS) * CALIBRATION_BANDWIDTH_MBPS
        print(f"推算实际带宽上限: {estimated_bandwidth_mbps:.2f} Mbps "
              f"(基准 {CALIBRATION_PPS:.0f} pps -> {CALIBRATION_BANDWIDTH_MBPS:.0f} Mbps)")

        # 安全使用带宽 = 实际带宽 × 使用比例，且不低于默认值
        safe_mbps = max(estimated_bandwidth_mbps * BANDWIDTH_USAGE, DEFAULT_BANDWIDTH_MBPS)
        safe_mbps = math.floor(safe_mbps)

        print(f"按 {BANDWIDTH_USAGE*100:.0f}% 安全使用带宽: {safe_mbps} Mbps")
        return safe_mbps

    except Exception as exc:
        print(f"从文件读取并计算带宽时发生错误: {exc}")
        return DEFAULT_BANDWIDTH_MBPS


def run_ksubdomain(bandwidth_mbps):
    bandwidth_param = f"{max(int(math.floor(bandwidth_mbps)), DEFAULT_BANDWIDTH_MBPS)}m"
    print(f"ksubdomain 使用带宽参数: {bandwidth_param}")

    command1 = [
        r".\tools\ksubdomain\ksubdomain.exe",
        "-dl", KDOMAIN_FILE,
        "-skip-wild",
        "-f", FIRST_DICT,
        "-b", bandwidth_param,
        "-o", OUTPUT_FILE,
    ]
    print(f"正在运行第一次 ksubdomain.exe... 命令：{subprocess.list2cmdline(command1)}")
    execute_command(command1)

    time.sleep(3)

    command2 = [
        r".\tools\ksubdomain\ksubdomain.exe",
        "-dl", KDOMAIN_FILE,
        "-skip-wild",
        "-f", SECOND_DICT,
        "-b", bandwidth_param,
        "-o", OUTPUT_FILE,
    ]
    print(f"正在运行第二次 ksubdomain.exe... 命令：{subprocess.list2cmdline(command2)}")
    execute_command(command2)


def execute_command(command):
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
        )

        for line in process.stdout:
            print(line, end="")
            sys.stdout.flush()

        process.wait()
        if process.returncode != 0:
            print(f"命令执行失败，退出码：{process.returncode}")
        else:
            print("命令执行成功。")
    except Exception as exc:
        print(f"运行命令时出错: {exc}")


def main():
    copy_domains()
    run_ksubdomain_test()
    bandwidth_mbps = calculate_bandwidth_from_file(TEST_OUTPUT_FILE)
    run_ksubdomain(bandwidth_mbps)


if __name__ == "__main__":
    main()
