import subprocess
import os
import re
from collections import Counter


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def is_valid_ip(ip):
    """检查 IP 地址是否有效"""
    ip_pattern = r'^\d{1,3}(\.\d{1,3}){3}$'
    if re.match(ip_pattern, ip):
        return all(0 <= int(part) < 256 for part in ip.split('.'))
    return False

def clean_ip_file(ip_file):
    """清理无效的 IP 地址"""
    valid_ips = []
    with open(ip_file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if is_valid_ip(line):
                valid_ips.append(line)
            else:
                print(f"无效 IP 地址：{line}")
    
    # 将清理后的 IP 地址写回文件
    with open(ip_file, 'w', encoding='utf-8', errors='replace', newline='\n') as f:
        for ip in valid_ips:
            f.write(f"{ip}\n")
    print(f"无效 IP 地址已被移除，更新后的 IP 文件为：{ip_file}")

def run_masscan():
    """运行 masscan 扫描并保存结果到 masscan.txt"""
    masscan_exe = r'.\tools\masscan\masscan.exe'  # masscan.exe 的路径
    ip_file = r'.\tools\masscan\ip.txt'  # 输入的 IP 文件路径
    output_file = r'.\tools\masscan\masscan.txt'  # 扫描结果保存的文件路径
    ports = '21,22,23,135,445,389,3389,80,443,8080,7001,3306,1433,1521,6379,27017,2375,5900,5432,4899'  # 端口列表
    rate = 100  # 扫描速率

    # 清理无效的 IP 地址
    clean_ip_file(ip_file)
    
    # 构造命令
    command = [masscan_exe, '-iL', ip_file, '-Pn', '-p', ports, '-oL', output_file, '--rate', str(rate)]
    
    try:
        print(f"正在执行 Masscan 命令: {' '.join(command)}")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
        )
        
        # 获取命令执行的输出
        stdout, stderr = process.communicate()

        # 打印标准输出和错误输出
        if stdout:
            print("Masscan 执行过程输出:")
            print(stdout)
        if stderr:
            print("Masscan 错误输出:")
            print(stderr)
        
        # 检查返回码
        if process.returncode == 0:
            print(f"Masscan 扫描完成，结果保存在: {output_file}")
        else:
            print(f"Masscan 扫描失败，返回码: {process.returncode}")

    except Exception as e:
        print(f"执行 masscan 时发生错误: {e}")

def process_masscan_results():
    """处理 masscan 扫描结果，统计 IP 地址出现次数大于 10 的 IP"""
    masscan_file = r'.\tools\masscan\masscan.txt'  # masscan 扫描结果文件路径
    output_file = r'.\tools\masscan\ip2.txt'  # 统计结果保存为 ip2.txt 文件

    # 检查 masscan.txt 文件是否存在
    if not os.path.exists(masscan_file):
        print(f"Masscan 扫描结果文件未找到: {masscan_file}")
        return

    ip_addresses = []
    # 定义正则表达式来匹配 IP 地址
    ip_pattern = r'\d+\.\d+\.\d+\.\d+'

    # 读取 masscan 扫描结果文件，提取 IP 地址
    with open(masscan_file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith("open"):
                # 提取 IP 地址
                ip_matches = re.findall(ip_pattern, line)
                if ip_matches:
                    ip_addresses.append(ip_matches[0])  # 取第一个匹配的 IP

    # 统计 IP 地址出现次数
    ip_counts = Counter(ip_addresses)

    # 过滤出出现次数大于 10 的 IP 地址
    filtered_ips = {ip: count for ip, count in ip_counts.items() if count > 10}

    # 打印出统计结果
    print(f"出现次数大于 10 的 IP 地址：")
    for ip, count in filtered_ips.items():
        print(f"{ip}: {count} 次")

    # 保存统计结果到 ip2.txt 文件
    with open(output_file, 'w', encoding='utf-8', errors='replace', newline='\n') as f:
        for ip in filtered_ips:
            f.write(f"{ip}\n")

    print(f"IP 地址统计完成，出现次数大于 10 的 IP 已保存到 {output_file}")

if __name__ == "__main__":
    run_masscan()  # 执行 masscan 扫描
    process_masscan_results()  # 处理扫描结果并保存到 ip2.txt
