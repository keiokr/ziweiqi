import os
from encoding_utils import read_lines_guess
from fscan_utils import normalize_ipv4_lines
from step16_merge_filter_ip import should_filter_ip
 
def remove_ips_from_file():
    """去除泛端口 IP，并在写入 fscan/ip.txt 前做最终 IPv4 去重和格式校验。"""
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

    # 读取 ip.txt 文件中的 IP 地址，并做最终格式校验与去重兜底。
    ip_addresses, invalid_ips, duplicate_count = normalize_ipv4_lines(read_lines_guess(ip_file))

    # 从 ip.txt 中去除在 ip2.txt 中出现的 IP 地址，并再次复用原有业务过滤规则兜底。
    filtered_ips = [
        ip for ip in ip_addresses
        if ip not in ip2_addresses and not should_filter_ip(ip)
    ]

    # 保存过滤后的 IP 地址到 fscan/ip.txt
    with open(output_file, 'w', encoding='utf-8') as f:
        for ip in filtered_ips:
            f.write(f"{ip}\n")

    print(
        f"IP 地址已去除，结果已保存到 {output_file}；"
        f"fscan 最终 IP 数: {len(filtered_ips)}，"
        f"去重: {duplicate_count}，非法: {len(invalid_ips)}"
    )
    if invalid_ips:
        print(f"已跳过非法 IP 示例: {', '.join(invalid_ips[:10])}")

if __name__ == "__main__":
    remove_ips_from_file()  # 执行去除操作
