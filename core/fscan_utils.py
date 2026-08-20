from __future__ import annotations

import datetime as _dt
import ipaddress
import re
from pathlib import Path

from encoding_utils import read_text_guess


PORT_TOKEN_RE = re.compile(r"\d{1,5}(?:-\d{1,5})?")


def normalize_ipv4_lines(lines):
    """
    fscan 最终输入前的 IPv4 兜底校验：
    - 去掉空白行和首尾空格；
    - 只保留合法 IPv4；
    - 按首次出现顺序去重。

    这里仅负责格式校验和去重；内网/CDN/高防等业务过滤规则继续由
    step16_merge_filter_ip.py 的 should_filter_ip() 负责，避免遗漏原有功能。
    """
    seen = set()
    valid_ips = []
    invalid_ips = []
    duplicate_count = 0

    for raw in lines:
        ip = str(raw).strip()
        if not ip:
            continue
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            invalid_ips.append(ip)
            continue
        if parsed.version != 4:
            invalid_ips.append(ip)
            continue
        normalized = str(parsed)
        if normalized in seen:
            duplicate_count += 1
            continue
        seen.add(normalized)
        valid_ips.append(normalized)

    return valid_ips, invalid_ips, duplicate_count


def rewrite_ipv4_file(path):
    """读取并重写 IP 文件，返回 (有效 IP 数, 无效 IP 列表, 重复数量)。"""
    file_path = Path(path)
    lines = read_text_guess(file_path).splitlines()
    valid_ips, invalid_ips, duplicate_count = normalize_ipv4_lines(lines)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(("\n".join(valid_ips) + "\n") if valid_ips else "", encoding="utf-8")
    return len(valid_ips), invalid_ips, duplicate_count


def _normalize_port_token(token):
    token = str(token).strip().strip(",")
    if not token or not PORT_TOKEN_RE.fullmatch(token):
        return None
    if "-" in token:
        start_text, end_text = token.split("-", 1)
        start = int(start_text)
        end = int(end_text)
        if start < 1 or end > 65535 or start > end:
            return None
        return f"{start}-{end}"
    port = int(token)
    if port < 1 or port > 65535:
        return None
    return str(port)


def normalize_ports_text(text):
    """
    fscan 最终输入前的端口兜底校验：
    - 支持逗号、空白、多行混合；
    - 支持合法端口范围，例如 8000-9000；
    - 过滤 0、>65535、反向范围和非法字符；
    - 按首次出现顺序去重。
    """
    seen = set()
    valid_ports = []
    invalid_ports = []
    duplicate_count = 0

    for raw_token in re.split(r"[\s,]+", text or ""):
        if not raw_token.strip():
            continue
        port = _normalize_port_token(raw_token)
        if port is None:
            invalid_ports.append(raw_token.strip())
            continue
        if port in seen:
            duplicate_count += 1
            continue
        seen.add(port)
        valid_ports.append(port)

    return valid_ports, invalid_ports, duplicate_count


def read_normalized_ports(path):
    """读取端口文件并返回 (端口列表, 无效项列表, 重复数量)。"""
    return normalize_ports_text(read_text_guess(path))


def rewrite_ports_file(path, *, separator=","):
    """读取并重写端口文件，返回 (有效端口数, 无效项列表, 重复数量)。"""
    file_path = Path(path)
    valid_ports, invalid_ports, duplicate_count = read_normalized_ports(file_path)
    if separator == "\n":
        content = ("\n".join(valid_ports) + "\n") if valid_ports else ""
    else:
        content = (separator.join(valid_ports) + "\n") if valid_ports else ""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return len(valid_ports), invalid_ports, duplicate_count


def make_run_log_path(prefix: str, *, directory: str | Path = r".\results\tmp") -> Path:
    """生成本次运行日志文件路径，统一落到 results/tmp。"""
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(prefix)).strip("_") or "fscan"
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    directory_path = Path(directory)
    directory_path.mkdir(parents=True, exist_ok=True)
    return directory_path / f"{safe_prefix}_{timestamp}.log"
