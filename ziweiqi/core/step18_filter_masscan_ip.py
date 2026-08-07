import os
from encoding_utils import read_lines_guess

def remove_ips_from_file():
    """去除 ip.txt 中包含在 ip2.txt 中的 IP 地址，去掉空白行和首尾空格，并保存到 fscan/ip.txt"""
    ip_file = r'.\tools\masscan\ip.txt'  # 输入的 IP 文件路径
    ip2_file = r'.\tools\masscan\ip2.txt'  # 要去除的 IP 文件路径
    output_file = r'.\tools\fscan\ip.txt'  # 输出的 IP 文件路径

    # 检查输入文件和输出目录是否存在
    if not os.path.exists(ip_file):
        print(f"文件未找到: {ip_file}")
        return
    if not os.path.exists(ip2_file):
        print(f"文件未找到: {ip2_file}")
        return
    os.makedirs(os.path.dirname(output_file), exist_ok=True)  # 确保输出目录存在

    # 读取 ip2.txt 文件中的 IP 地址
    ip2_addresses = set(line.strip() for line in read_lines_guess(ip2_file) if line.strip())  # 去掉空白行并去除首尾空格

    # 读取 ip.txt 文件中的 IP 地址
    ip_addresses = [line.strip() for line in read_lines_guess(ip_file) if line.strip()]  # 去掉空白行并去除首尾空格

    # 从 ip.txt 中去除在 ip2.txt 中出现的 IP 地址
    filtered_ips = [ip for ip in ip_addresses if ip not in ip2_addresses]

    # 保存过滤后的 IP 地址到 fscan/ip.txt
    with open(output_file, 'w', encoding='utf-8') as f:
        for ip in filtered_ips:
            f.write(f"{ip}\n")

    print(f"IP 地址已去除，结果已保存到 {output_file}")

if __name__ == "__main__":
    remove_ips_from_file()  # 执行去除操作
