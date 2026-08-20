#!/usr/bin/env python 
# coding:utf-8

from socket import getaddrinfo, gethostbyname
import ipaddress
import os
import time
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOMAIN = os.path.join(BASE_DIR, "url.txt")
RESULT_FILE = os.path.join(BASE_DIR, "result.txt")
YICHANG_FILE = os.path.join(BASE_DIR, "yichang.txt")
ERROR_FILE = os.path.join(BASE_DIR, "error.txt")


def safe_print(message):
    """\u63a7\u5236\u53f0\u53ea\u8f93\u51fa ASCII\uff0c\u907f\u514d\u5916\u5c42\u6267\u884c\u5668\u7528 GBK \u89e3\u7801 UTF-8 \u8f93\u51fa\u65f6\u62a5\u9519"""
    try:
        text = str(message).encode("ascii", errors="backslashreplace").decode("ascii")
        print(text, flush=True)
    except Exception:
        try:
            print("log output failed", flush=True)
        except Exception:
            pass

# \u5e38\u7528\u7684DNS\u3001CDN\u3001DDoS\u548cDamddos\u5730\u5740\uff0c\u5305\u62ec\u963f\u91cc\u4e91 WAF \u548c CDN \u5730\u5740\u6bb5
COMMON_CDN_DNS = {
    # DNS
    "1.1.1.1",  # Cloudflare DNS
    "1.0.0.1",  # Cloudflare DNS
    "8.8.8.8",  # Google DNS
    "8.8.4.4",  # Google DNS
    "114.114.114.114",  # 114DNS
    "223.5.5.5",  # Alibaba DNS
    "223.6.6.6",  # Alibaba DNS

    # \u5e38\u89c1CDN\u5730\u5740
    "104.16.0.0/12",  # Cloudflare CDN
    "172.67.0.0/16",  # Cloudflare
    "104.21.0.0/16",  # Cloudflare
    "139.9.0.0/16",   # \u963f\u91cc\u4e91 CDN
    "139.224.0.0/12", # \u963f\u91cc\u4e91 CDN
    "117.27.0.0/16",  # \u963f\u91cc\u4e91 CDN
    "185.222.200.0/22", # \u963f\u91cc\u4e91 CDN

    # \u963f\u91cc\u4e91 WAF \u548c CDN \u7684\u76f8\u5173\u5730\u5740\u6bb5
    "47.100.0.0/16",
    "101.37.42.0/24",
    "101.37.44.0/24",
    "39.156.0.0/16",
    "114.215.0.0/16",

    # DDoS\u76f8\u5173\u5730\u5740
    "45.32.0.0/16",  # DDoS\u9632\u62a4\u670d\u52a1\u5546\u5730\u5740
    "185.208.169.0/24", # DDoS\u9632\u62a4
    "104.236.0.0/14",  # DigitalOcean DDoS\u4fdd\u62a4
    "192.64.147.0/24",  # ProxyDDoS
    "185.222.204.0/22", # DDoS\u9632\u62a4

    # Damddos\u76f8\u5173\u5730\u5740
    "103.11.188.0/22", # Damddos

    # \u4e2d\u56fd\u4e3b\u6d41CDN
    "39.156.66.0/24",  # \u817e\u8baf\u4e91 CDN
    "116.62.134.0/24", # \u534e\u4e3a\u4e91 CDN
    "103.45.223.0/24", # \u4e03\u725b\u4e91
    "182.92.0.0/16",   # \u767e\u5ea6\u4e91 CDN
    "139.196.0.0/16",  # \u4eac\u4e1c\u4e91 CDN
    "118.178.0.0/16",  # \u53cb\u76df CDN
    "101.200.0.0/16",  # \u4e91\u6d4b CDN
}

def build_common_networks():
    """\u9884\u7f16\u8bd1 CDN/DNS \u5730\u5740\u6bb5\uff0c\u907f\u514d\u5355\u884c\u5f02\u5e38\u5bfc\u81f4\u811a\u672c\u4e2d\u65ad"""
    networks = []
    for net in COMMON_CDN_DNS:
        try:
            networks.append(ipaddress.ip_network(net, strict=False))
        except Exception:
            pass
    return tuple(networks)


COMMON_CDN_DNS_NETWORKS = build_common_networks()


def get_local_ips():
    """\u83b7\u53d6\u672c\u673a\u5730\u5740\uff1b\u5931\u8d25\u65f6\u8fd4\u56de\u5df2\u83b7\u53d6\u5230\u7684\u90e8\u5206\uff0c\u7edd\u4e0d\u4e2d\u65ad\u811a\u672c"""
    ips = set()
    for host in ["localhost", "127.0.0.1"]:
        try:
            ips.add(gethostbyname(host))
        except Exception:
            pass
    return ips


# \u83b7\u53d6\u672c\u673a\u5730\u5740
local_ips = get_local_ips()

def is_private_ip(ip):
    """\u5224\u65adIP\u5730\u5740\u662f\u5426\u662f\u5185\u7f51\u5730\u5740"""
    try:
        return ipaddress.ip_address(ip).is_private
    except Exception:
        return False

def is_common_cdn_dns(ip):
    """\u68c0\u67e5IP\u662f\u5426\u5c5e\u4e8e\u5e38\u7528\u7684CDN\u6216DNS\u5730\u5740"""
    try:
        address = ipaddress.ip_address(ip)
    except Exception:
        return False

    for net in COMMON_CDN_DNS_NETWORKS:
        try:
            if address.version == net.version and address in net:
                return True
        except Exception:
            continue
    return False


def read_domain_lines(path):
    """\u517c\u5bb9\u591a\u79cd\u6587\u672c\u7f16\u7801\u8bfb\u53d6 url.txt\uff1b\u5168\u90e8\u5931\u8d25\u65f6\u4f7f\u7528\u66ff\u6362\u6a21\u5f0f\uff0c\u4fdd\u8bc1\u4e0d\u56e0\u7f16\u7801\u4e2d\u65ad"""
    encodings = [
        "utf-8-sig",
        "utf-8",
        "gb18030",
        "gbk",
        "cp936",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "big5",
    ]

    with open(path, "rb") as f:
        raw = f.read()

    if not raw:
        return [], "empty"

    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            # UTF-16/UTF-32 \u6587\u4ef6\u5982\u679c\u88ab UTF-8 \u8bef\u8bfb\uff0c\u901a\u5e38\u4f1a\u51fa\u73b0\u5927\u91cf \x00\u3002
            # \u9047\u5230\u8fd9\u79cd\u60c5\u51b5\uff0c\u7ee7\u7eed\u5c1d\u8bd5\u540e\u7eed\u7f16\u7801\u3002
            if encoding not in {"utf-16", "utf-16-le", "utf-16-be"}:
                sample = text[:1000]
                if sample and sample.count("\x00") / len(sample) > 0.05:
                    continue
            return text.splitlines(), encoding
        except UnicodeDecodeError:
            continue
        except Exception:
            continue

    # \u6700\u540e\u515c\u5e95\uff1a\u5b81\u53ef\u628a\u574f\u5b57\u7b26\u66ff\u6362\u6389\uff0c\u4e5f\u4e0d\u8ba9\u811a\u672c\u5d29\u6e83
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines(), "utf-8-replace"


def normalize_domain(line):
    """\u6e05\u6d17\u6bcf\u4e00\u884c\uff0c\u517c\u5bb9\u57df\u540d\u3001URL\u3001host:port\uff1b\u5f02\u5e38\u8f93\u5165\u8fd4\u56de\u7a7a\u5b57\u7b26\u4e32"""
    try:
        value = str(line).strip().strip("\ufeff")
        if not value or value.startswith("#"):
            return ""

        # \u5982\u679c\u4e00\u884c\u91cc\u5e26\u4e86\u5907\u6ce8\uff0c\u53ea\u53d6\u7b2c\u4e00\u5217
        value = value.split()[0].strip()
        if not value:
            return ""

        if "://" in value:
            parsed = urlparse(value)
        else:
            # \u8ba9 urlparse \u6b63\u786e\u5904\u7406 example.com:443\u3001[::1]:443 \u7b49\u5f62\u5f0f
            parsed = urlparse("//" + value)

        host = parsed.hostname or value
        host = host.strip().strip(".").strip()
        if not host:
            return ""

        # \u4e2d\u6587\u57df\u540d\u5c3d\u91cf\u8f6c punycode\uff0c\u5931\u8d25\u5219\u7ee7\u7eed\u4f7f\u7528\u539f\u503c
        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass

        return host
    except Exception:
        return ""


def safe_write(file_obj, message):
    """\u5199\u6587\u4ef6\u5931\u8d25\u4e5f\u4e0d\u4e2d\u65ad\u4e3b\u6d41\u7a0b"""
    try:
        file_obj.write(message)
        file_obj.flush()
    except Exception:
        pass


def log_error(ERR, domain, error):
    """\u7edf\u4e00\u8bb0\u5f55\u9519\u8bef\uff1b\u8bb0\u5f55\u5931\u8d25\u65f6\u53ea\u6253\u5370\uff0c\u4e0d\u629b\u51fa"""
    safe_write(ERR, f"{domain}: {error}\n")


def main():
    try:
        lines, detected_encoding = read_domain_lines(DOMAIN)
    except Exception as e:
        safe_print(f"read {DOMAIN} failed: {e}")
        safe_print("script finished safely.")
        time.sleep(3)
        return

    try:
        result = open(RESULT_FILE, "a+", encoding="utf-8", errors="replace")
        yichang = open(YICHANG_FILE, "a+", encoding="utf-8", errors="replace")
        ERR = open(ERROR_FILE, "a+", encoding="utf-8", errors="replace")
    except Exception as e:
        safe_print(f"open output file failed: {e}")
        safe_print("script finished safely.")
        time.sleep(3)
        return

    with result, yichang, ERR:
        total = len(lines)

        # \u5f00\u59cb\u5904\u7406
        safe_print(f"url.txt encoding: {detected_encoding}")
        safe_print(f"total lines: {total}, start processing...")

        for index, line in enumerate(lines):
            domain = normalize_domain(line)
            try:
                if not domain:
                    continue

                addr_info = getaddrinfo(domain, None)
                ip_addresses = {info[4][0] for info in addr_info if info and len(info) >= 5 and info[4]}

                if not ip_addresses:
                    log_error(ERR, domain, "\u672a\u89e3\u6790\u5230 IP \u5730\u5740")
                    continue

                # \u89e3\u6790\u5230\u591a\u4e2aIP\u5730\u5740\u7684\u60c5\u51b5
                if len(ip_addresses) > 1:
                    safe_write(yichang, f"{domain} {' '.join(sorted(ip_addresses))}\n")
                    safe_print(f"multiple IP addresses: {domain}, saved to yichang.txt")
                    continue

                # \u8fc7\u6ee4\u51fa\u6b63\u5e38\u7684 IP \u548c\u9700\u8981\u5199\u5165 yichang.txt \u7684 IP
                yichang_ips = [
                    ip for ip in ip_addresses
                    if is_private_ip(ip) or ip in local_ips or is_common_cdn_dns(ip)
                ]

                # \u6b63\u5e38\u7684 IP \u5730\u5740
                filtered_ips = [
                    ip for ip in ip_addresses
                    if not (is_private_ip(ip) or ip in local_ips or is_common_cdn_dns(ip))
                ]

                if filtered_ips:
                    safe_write(result, f"{domain} {' '.join(sorted(filtered_ips))}\n")

                if yichang_ips:
                    safe_write(yichang, f"{domain} {' '.join(sorted(yichang_ips))}\n")

                # \u663e\u793a\u5904\u7406\u8fdb\u5ea6
                progress = (index + 1) / total * 100 if total else 100
                safe_print(f"progress: {index + 1}/{total} ({progress:.2f}%) - domain: {domain}")
            except Exception as e:
                log_error(ERR, domain or str(line).strip(), str(e))
                safe_print(f"error processing {domain or str(line).strip()}, saved to error.txt, continue")
                continue

        # \u5904\u7406\u5b8c\u6210\u540e\u7b49\u5f85 3 \u79d2
        safe_print("all domains processed, wait 3 seconds...")
        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("keyboard interrupt, script exited safely.")
    except Exception as e:
        # \u6700\u5916\u5c42\u515c\u5e95\uff0c\u907f\u514d\u663e\u793a traceback \u5bfc\u81f4\u7528\u6237\u8bef\u4ee5\u4e3a\u811a\u672c\u5d29\u6e83
        try:
            with open(ERROR_FILE, "a+", encoding="utf-8", errors="replace") as ERR:
                ERR.write(f"\u5168\u5c40\u5f02\u5e38: {e}\n")
        except Exception:
            pass
        safe_print(f"global exception captured: {e}")
