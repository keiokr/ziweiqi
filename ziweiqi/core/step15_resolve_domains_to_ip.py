import shutil
import subprocess
import os
import sys
import time  # 导入 time 模块以支持延时
import re  # 导入正则表达式模块

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def copy_file():
    """复制 zzzok.txt 到 domaintoIP/url.txt"""
    source_file = os.path.join(PROJECT_ROOT, "results", "tmp", "23_ziyumingcore_2.txt")
    destination_file = os.path.join(PROJECT_ROOT, "tools", "domaintoIP", "url.txt")
    
    # 确保源文件存在
    if not os.path.exists(source_file):
        print(f"源文件 {source_file} 不存在，请检查路径。")
        return

    try:
        shutil.copy(source_file, destination_file)
        print(f"文件 {source_file} 成功复制到 {destination_file}")
    except Exception as e:
        print(f"复制文件时发生错误: {e}")

def run_domaintoip_script():
    """运行 domaintoIP/domaintoip.py 脚本，并实时显示输出"""
    command = [sys.executable, os.path.join(PROJECT_ROOT, "tools", "domaintoIP", "domaintoip.py")]
    
    try:
        # 合并读取 stdout/stderr，避免子进程输出过多时发生阻塞
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT,
            env=child_env(),
        ) as proc:
            for output in proc.stdout:
                if output:
                    print(output.strip())

            proc.wait()

        if proc.returncode == 0:
            print("domaintoip.py 脚本执行成功")
        else:
            print(f"domaintoip.py 脚本执行失败，退出码: {proc.returncode}")
    except Exception as e:
        print(f"执行脚本时发生错误: {e}")

def extract_ip():
    """提取 domaintoIP/result.txt 中的 IP，去除空白行并去重，只保留 IP 地址"""
    input_file = os.path.join(PROJECT_ROOT, "tools", "domaintoIP", "result.txt")
    output_file = os.path.join(PROJECT_ROOT, "results", "tmp", "25_ip2.txt")

    # 确保输入文件存在
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在，请检查路径。")
        return

    # 存储去重后的 IP
    ip_addresses = set()

    # IP 地址的正则表达式，用来匹配有效的 IPv4 地址
    ip_pattern = re.compile(r"(\d{1,3}\.){3}\d{1,3}")  # 匹配类似 192.168.1.1 的地址

    try:
        # 打开并读取 result.txt 文件
        with open(input_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()  # 去除前后空格
                if line:  # 去除空白行
                    # 使用正则表达式查找 IP 地址
                    match = ip_pattern.search(line)
                    if match:
                        ip_addresses.add(match.group())  # 提取匹配到的 IP 地址并去重

        # 将去重后的 IP 地址写入 ip2.txt
        with open(output_file, "w", encoding="utf-8") as f:
            for ip in ip_addresses:
                f.write(ip + "\n")

        print(f"提取完成，结果已保存到 {output_file}")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")

if __name__ == "__main__":
    copy_file()  # 复制文件
    run_domaintoip_script()  # 执行脚本
    extract_ip()  # 提取并保存 IP 地址
