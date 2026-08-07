import os
import ipaddress

# ========== 可随意添加的“随手IP” ==========

CUSTOM_FILTER_IPS = {

     }

CUSTOM_FILTER_IPS = {
    "1.2.3.4",
    "5.6.7.8",
    "2.2.2.2",
    "3.3.3.3",
    "4.4.4.4",
    "5.5.5.5",
    "6.6.6.6",
    "7.7.7.7",
    "9.9.9.9",
}
# ========== 预设的过滤IP（DNS、CDN、高防等） ==========
PRESET_FILTER_IPS = {
    # ---------- 常见公共DNS ----------
    "8.8.8.8", "8.8.4.4",           # Google DNS
    "114.114.114.114", "114.114.115.115",  # 114 DNS
    "223.5.5.5", "223.6.6.6",       # 阿里DNS
    "180.76.76.76",                  # 百度DNS
    "1.1.1.1", "1.0.0.1",           # Cloudflare DNS
    "119.29.29.29",                  # DNSPod DNS
    
    # ---------- Cloudflare CDN [citation:1][citation:8] ----------
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/17",
    "172.64.128.0/19",
    
    # ---------- 阿里云 DDoS 高防回源网段 [citation:6] ----------
    # 中国内地 DDoS 高防
    "8.145.214.0/24",
    # 非中国内地 DDoS 高防
    "47.242.97.0/24",
    "8.220.123.0/24",
    "8.211.227.0/24",
    "47.253.67.0/24",
    "47.89.206.0/24",
    "8.221.128.0/24",
    "8.215.149.0/24",
    "47.250.62.0/24",
    
    # ---------- 腾讯云 CDN [citation:8] ----------
    "58.250.143.0/24",
    "58.251.121.0/24",
    "59.36.120.0/24",
    "61.151.163.0/24",
    "101.227.163.0/24",
    "111.161.109.0/24",
    "116.128.128.0/24",
    "123.151.76.0/24",
    "125.39.46.0/24",
    "140.207.120.0/24",
    "180.163.22.0/24",
    "183.3.254.0/24",
    "223.166.151.0/24",
    
    # ---------- 加速乐 CDN [citation:8] ----------
    "113.107.238.0/24",
    "106.42.25.0/24",
    "183.222.96.0/24",
    "117.21.219.0/24",
    "116.55.250.0/24",
    "111.202.98.0/24",
    "111.13.147.0/24",
    "122.228.238.0/24",
    "58.58.81.0/24",
    "1.31.128.0/24",
    "123.125.115.0/24",
    "120.208.57.0/24",
    "120.208.58.0/24",
    "114.239.159.0/24",
    "114.239.160.0/24",
    "114.239.161.0/24",
    "114.239.162.0/24",
    "114.239.163.0/24",
    "114.239.164.0/24",
    
    # ---------- 常见高防IP段 [citation:2] ----------
    "123.56.0.0/14",      # DDoS高防段
    "121.40.0.0/14",      # DDoS高防段
    "47.92.0.0/14",       # DDoS高防段
    "115.182.0.0/16",     # CDN高防段
    "117.34.0.0/16",      # CDN高防段
    "101.201.0.0/16",     # CDN高防段
    "202.97.56.0/21",     # BGP高防段
    "202.97.60.0/22",     # BGP高防段
    
    # ---------- Cloudguard 高防IP [citation:4] ----------
    "185.231.114.0/24",
    "185.105.237.0/24",
    "89.187.167.225",
    
    # ---------- AWS CloudFront CDN（示例段，完整列表见AWS官方JSON）[citation:5] ----------
    "3.10.17.128/25",
    "3.11.53.0/24",
    "3.35.130.128/25",
    "13.32.0.0/15",       # CloudFront常用段
    "13.224.0.0/14",      # CloudFront常用段
    "54.230.0.0/16",      # CloudFront常用段
    "52.40.35.5",         # 俄勒冈Synthetic Server [citation:5]
    "52.201.103.47",      # 弗吉尼亚Synthetic Server [citation:5]
    "52.48.243.82",       # 法兰克福Synthetic Server [citation:5]
    
    # ---------- 其他CDN/高防补充 ----------
    "104.16.0.0",         # 原示例CDN IP
    "47.91.0.0",          # 原示例高防IP
}

# 合并所有需要过滤的精确IP/CIDR
FILTER_IPS = PRESET_FILTER_IPS | CUSTOM_FILTER_IPS

def ip_in_cidr(ip_str, cidr_str):
    """判断IP是否在CIDR范围内"""
    try:
        ip = ipaddress.ip_address(ip_str)
        network = ipaddress.ip_network(cidr_str, strict=False)
        return ip in network
    except ValueError:
        return False

def is_private_ip(ip_str):
    """判断是否为私有IP地址（内网IP、回环、链路本地等）"""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return True
        if ip.is_multicast or ip.is_unspecified:
            return True
        return False
    except ValueError:
        return True  # 无效IP，过滤掉

def should_filter_ip(ip_str):
    """判断IP是否应该被过滤（支持内网IP、精确IP、CIDR匹配）"""
    if not ip_str:
        return True
    # 内网IP过滤
    if is_private_ip(ip_str):
        print(f"过滤内网IP: {ip_str}")
        return True
    # 黑名单过滤（支持精确IP和CIDR）
    for f in FILTER_IPS:
        if '/' in f:  # CIDR格式
            if ip_in_cidr(ip_str, f):
                print(f"过滤 {ip_str} (匹配CIDR {f})")
                return True
        else:  # 精确IP
            if ip_str == f:
                print(f"过滤黑名单IP: {ip_str}")
                return True
    return False

def merge_ip_files():
    """合并IP文件，去重并过滤"""
    ip_files = ['.\\results\\tmp\\6_ip.txt', '.\\results\\tmp\\25_ip2.txt']
    ip_addresses = set()

    print(f"已加载 {len(FILTER_IPS)} 条过滤规则（含CIDR段）")

    for ip_file in ip_files:
        try:
            with open(ip_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    ip = line.strip()
                    if ip and not should_filter_ip(ip):
                        ip_addresses.add(ip)
        except FileNotFoundError:
            print(f"{ip_file} 文件未找到，跳过该文件。")
            continue
        except Exception as e:
            print(f"读取 {ip_file} 时出错: {e}")
            continue

    # 创建目标目录
    output_dir = '.\\tools\\masscan'
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'ip.txt')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for ip in ip_addresses:
                f.write(ip + "\n")
        print(f"已过滤并合并 {len(ip_addresses)} 个IP，保存到 {output_file}")
    except Exception as e:
        print(f"写入文件时出错: {e}")

if __name__ == "__main__":
    merge_ip_files()