#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import queue
import re
import socket
import ssl
import threading
import time
import ipaddress
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog, scrolledtext


def read_text_guess(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            pass
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path: str, text: str):
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(text)


def lines(text: str):
    return [x.strip() for x in text.splitlines() if x.strip()]


DEFAULT_THREADS = 100
TIMEOUT_CONNECT = 1.2
TIMEOUT_RECV = 1.5
MAX_BANNER_SIZE = 512

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 993, 995, 1433, 1521, 3306, 3389, 5432, 6379, 8080, 8443, 9090, 27017]
WEB_PORTS = {80, 443, 8080, 8443, 8000, 8888, 3000, 5000, 7001, 9090}
HTTPS_PORTS = {443, 8443}

COMMON_CDN_SINGLE_IPS = {
    "1.1.1.1", "1.0.0.1",
    "8.8.8.8", "8.8.4.4",
    "114.114.114.114", "223.5.5.5", "223.6.6.6",
}

COMMON_CDN_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in [
        "104.16.0.0/12", "172.67.0.0/16", "104.21.0.0/16",
        "139.9.0.0/16", "139.224.0.0/12", "117.27.0.0/16",
        "185.222.200.0/22", "47.100.0.0/16",
        "101.37.42.0/24", "101.37.44.0/24",
        "39.156.0.0/16", "114.215.0.0/16",
        "45.32.0.0/16", "185.208.169.0/24",
        "104.236.0.0/14", "192.64.147.0/24", "185.222.204.0/22",
        "103.11.188.0/22", "39.156.66.0/24", "116.62.134.0/24",
        "103.45.223.0/24", "182.92.0.0/16", "139.196.0.0/16",
        "118.178.0.0/16", "101.200.0.0/16",
    ]
)

LOCAL_IPS = {"127.0.0.1", "::1"}


def get_all_ips(domain: str):
    try:
        _, _, ips = socket.gethostbyname_ex(domain.strip())
        if not ips:
            raise socket.gaierror("未找到 IP 地址")
        return ips
    except socket.gaierror as e:
        return [f"解析失败: {e}"]
    except Exception as e:
        return [f"未知错误: {e}"]


def is_ip_string(text: str) -> bool:
    try:
        ipaddress.ip_address(text.strip())
        return True
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def is_common_cdn_dns(ip: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if str(ip_obj) in COMMON_CDN_SINGLE_IPS:
        return True
    return any(ip_obj in net for net in COMMON_CDN_NETWORKS)


def resolve_all_ipv4(domain: str) -> list[str]:
    infos = socket.getaddrinfo(domain.strip(), None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    ips = []
    for info in infos:
        ip = info[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips


def resolve_domain(domain: str):
    try:
        ips = resolve_all_ipv4(domain)
    except Exception as e:
        raise RuntimeError(str(e))
    if len(ips) > 1:
        return [], ips
    normal, abnormal = [], []
    for ip in ips:
        if ip in LOCAL_IPS or is_private_ip(ip) or is_common_cdn_dns(ip):
            abnormal.append(ip)
        else:
            normal.append(ip)
    return normal, abnormal


def resolve_target(target: str):
    target = target.strip()
    if is_ip_string(target):
        return target, [target]
    try:
        return target, resolve_all_ipv4(target)
    except Exception:
        return target, []


def parse_http_response(raw_text: str):
    status_code = ""
    title = ""
    server = ""
    lines_ = raw_text.split("\r\n")
    if lines_ and lines_[0].startswith("HTTP/"):
        parts = lines_[0].split()
        if len(parts) >= 2:
            status_code = parts[1]
    m = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE | re.DOTALL)
    if m:
        title = " ".join(m.group(1).strip().split())
    m = re.search(r"^Server:\s*(.+)$", raw_text, re.IGNORECASE | re.MULTILINE)
    if m:
        server = m.group(1).strip()
    return status_code, title, server


def grab_banner(ip: str, port: int, stop_event: threading.Event, host_header: str = None):
    if stop_event.is_set():
        return "", "", "", ""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT_CONNECT)
        sock.connect((ip, port))
        sock.settimeout(TIMEOUT_RECV)
        conn = sock
        if port in WEB_PORTS:
            if port in HTTPS_PORTS:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                conn = context.wrap_socket(sock, server_hostname=host_header or ip)
            request_host = host_header or ip
            request = (
                f"GET / HTTP/1.0\r\n"
                f"Host: {request_host}\r\n"
                f"User-Agent: Mozilla/5.0\r\n"
                f"Accept: */*\r\n"
                f"Connection: close\r\n\r\n"
            )
            conn.send(request.encode())
            response = b""
            while not stop_event.is_set():
                try:
                    chunk = conn.recv(2048)
                    if not chunk:
                        break
                    response += chunk
                    if len(response) >= MAX_BANNER_SIZE:
                        break
                except socket.timeout:
                    break
            banner_text = response.decode(errors="replace")
            status_code, title, server = parse_http_response(banner_text)
            return banner_text[:MAX_BANNER_SIZE].strip(), status_code, title, server
        try:
            data = conn.recv(MAX_BANNER_SIZE)
        except socket.timeout:
            data = b""
        if not data:
            try:
                conn.send(b"\r\n")
                time.sleep(0.15)
                data = conn.recv(MAX_BANNER_SIZE)
            except Exception:
                data = b""
        banner_text = data.decode(errors="replace").strip()
        return banner_text[:MAX_BANNER_SIZE], "", "", ""
    except Exception as e:
        return f"连接错误: {e}", "", "", ""
    finally:
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass


def build_web_url(target, ip, port, scheme="auto"):
    host = target if not is_ip_string(target) else ip
    if scheme == "auto":
        scheme = "https" if port in (443, 8443) else "http"
    if scheme == "https" and port in (443, 8443):
        return f"https://{host}/"
    if scheme == "http" and port in (80, 8080, 8000, 8888, 3000, 5000, 7001, 9090):
        return f"http://{host}/"
    return f"{scheme}://{host}:{port}/"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("合并版网络工具")
        self.root.geometry("1440x900")
        self.root.minsize(1280, 820)
        self.apply_theme()

        self.normal_ip_set = set()
        self.ping_stop = threading.Event()
        self.resolve_stop = threading.Event()
        self.scan_stop = threading.Event()
        self.resolve_running = False
        self.ping_running = False
        self.scan_running = False
        self.scan_total = 0
        self.scan_done = 0
        self.scan_lock = threading.Lock()
        self.web_set = set()
        self.scan_results = []

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._tab_ping()
        self._tab_match()
        self._tab_scan()

    def apply_theme(self):
        family = "Microsoft YaHei UI"
        try:
            available = set(tkfont.families(self.root))
            if family not in available:
                family = "Microsoft YaHei" if "Microsoft YaHei" in available else "Segoe UI"
        except Exception:
            family = "Segoe UI"

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family=family, size=11)
        text_font = tkfont.Font(family=family, size=11)
        big_font = tkfont.Font(family=family, size=12)
        bold_font = tkfont.Font(family=family, size=12, weight="bold")

        self.root.option_add("*Font", default_font)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=default_font)
        style.configure("TButton", font=big_font, padding=(10, 6))
        style.configure("TLabel", font=big_font)
        style.configure("TLabelframe.Label", font=bold_font)
        style.configure("TNotebook.Tab", font=bold_font, padding=(16, 8))
        style.configure("Treeview", font=text_font, rowheight=28)
        style.configure("Treeview.Heading", font=bold_font)

        self.widget_font = text_font
        self.widget_font_big = big_font
        self.widget_font_bold = bold_font

    def _import_to(self, widget):
        path = filedialog.askopenfilename(title="选择文本文件", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path:
            try:
                widget.insert(tk.END, read_text_guess(path))
            except Exception as e:
                messagebox.showerror("导入错误", str(e))

    def _copy_clip(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _set_status(self, label, text, color="gray"):
        label.config(text=text, foreground=color)

    # ---------------- Ping ----------------
    def _tab_ping(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="域名解析")
        lf = ttk.LabelFrame(f, text="域名列表（每行一个）"); lf.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        self.ping_in = tk.Text(lf, height=8, wrap=tk.NONE, font=self.widget_font_big, padx=6, pady=6); self.ping_in.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sy = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.ping_in.yview); sy.pack(side=tk.RIGHT, fill=tk.Y)
        self.ping_in.config(yscrollcommand=sy.set)
        bf = ttk.Frame(f); bf.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(bf, text="导入文件", command=lambda: self._import_to(self.ping_in)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="清空输入", command=lambda: self.ping_in.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=3)
        self.ping_start = ttk.Button(bf, text="开始解析", command=self.start_ping); self.ping_start.pack(side=tk.LEFT, padx=3)
        self.ping_stop_btn = ttk.Button(bf, text="停止", command=self.stop_ping, state=tk.DISABLED); self.ping_stop_btn.pack(side=tk.LEFT, padx=3)
        self.ping_status = ttk.Label(bf, text="就绪", foreground="gray"); self.ping_status.pack(side=tk.RIGHT, padx=10)
        rf = ttk.LabelFrame(f, text="解析结果"); rf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        cols = ("domain", "ips", "status")
        self.ping_tree = ttk.Treeview(rf, columns=cols, show="headings", height=12)
        for c, t, w in [("domain", "域名", 280), ("ips", "IP 地址", 740), ("status", "状态", 100)]:
            self.ping_tree.heading(c, text=t); self.ping_tree.column(c, width=w, anchor=tk.W if c != "status" else tk.CENTER)
        sy = ttk.Scrollbar(rf, orient=tk.VERTICAL, command=self.ping_tree.yview); self.ping_tree.config(yscrollcommand=sy.set)
        self.ping_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sy.pack(side=tk.RIGHT, fill=tk.Y)

    def start_ping(self):
        if self.ping_running: return
        items = lines(self.ping_in.get("1.0", tk.END))
        if not items: return messagebox.showwarning("警告", "请输入至少一个域名")
        for i in self.ping_tree.get_children(): self.ping_tree.delete(i)
        self.ping_stop.clear(); self.ping_running = True
        self.normal_ip_set.clear()
        self.ping_start.config(state=tk.DISABLED); self.ping_stop_btn.config(state=tk.NORMAL)
        self._set_status(self.ping_status, "正在解析...", "blue")
        threading.Thread(target=self._ping_thread, args=(items,), daemon=True).start()

    def stop_ping(self):
        self.ping_stop.set(); self._set_status(self.ping_status, "正在停止...", "red")

    def _ping_thread(self, items):
        total = len(items)
        for i, d in enumerate(items, 1):
            if self.ping_stop.is_set(): break
            try:
                ips = get_all_ips(d)
                if len(ips) == 1 and (ips[0].startswith("解析失败:") or ips[0].startswith("未知错误:")):
                    status, iptxt = "失败", ips[0]
                else:
                    status, iptxt = "成功", ", ".join(ips)
            except Exception as e:
                status, iptxt = "失败", str(e)
            self.root.after(0, lambda d=d, iptxt=iptxt, status=status, i=i, total=total: self._ping_add(d, iptxt, status, i, total))
        self.root.after(0, self._ping_done)

    def _ping_add(self, d, iptxt, status, i, total):
        self.ping_tree.insert("", tk.END, values=(d, iptxt, status))
        if status == "成功":
            for ip in [x.strip() for x in iptxt.split(",") if x.strip()]:
                if is_ip_string(ip):
                    self.normal_ip_set.add(ip)
        self._set_status(self.ping_status, f"已完成 {i}/{total}", "blue")

    def _ping_done(self):
        self.ping_running = False
        self.ping_start.config(state=tk.NORMAL); self.ping_stop_btn.config(state=tk.DISABLED)
        self._set_status(self.ping_status, "已停止" if self.ping_stop.is_set() else "解析完成", "orange" if self.ping_stop.is_set() else "green")

    # ---------------- Resolve ----------------
    def _tab_resolve(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="域名解析")
        lf = ttk.LabelFrame(f, text="域名列表（每行一个域名）"); lf.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        self.res_in = scrolledtext.ScrolledText(lf, height=8, width=80); self.res_in.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        bf = ttk.Frame(lf); bf.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(bf, text="导入文件", command=lambda: self._import_to(self.res_in)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="清除输入", command=lambda: self.res_in.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=3)
        self.res_start = ttk.Button(bf, text="开始解析", command=self.start_resolve); self.res_start.pack(side=tk.LEFT, padx=3)
        self.res_stop_btn = ttk.Button(bf, text="停止解析", command=self.stop_resolve, state=tk.DISABLED); self.res_stop_btn.pack(side=tk.LEFT, padx=3)
        self.res_progress = ttk.Progressbar(f, length=400, mode="determinate"); self.res_progress.pack(fill=tk.X, padx=10, pady=5)
        n = ttk.Notebook(f); n.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.res_ok = scrolledtext.ScrolledText(n, wrap=tk.WORD); n.add(self.res_ok, text="正常 IP")
        self.res_bad = scrolledtext.ScrolledText(n, wrap=tk.WORD); n.add(self.res_bad, text="异常 IP")
        self.res_err = scrolledtext.ScrolledText(n, wrap=tk.WORD); n.add(self.res_err, text="错误信息")
        bf2 = ttk.Frame(f); bf2.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(bf2, text="导出解析结果", command=self.export_resolve).pack(side=tk.LEFT)
        self.res_status = ttk.Label(bf2, text="就绪", foreground="gray"); self.res_status.pack(side=tk.RIGHT, padx=10)

    def start_resolve(self):
        if self.resolve_running: return
        items = lines(self.res_in.get("1.0", tk.END))
        if not items: return messagebox.showwarning("无域名", "请先输入或导入域名。")
        self.res_ok.delete("1.0", tk.END); self.res_bad.delete("1.0", tk.END); self.res_err.delete("1.0", tk.END)
        self.normal_ip_set.clear(); self.resolve_stop.clear(); self.resolve_running = True
        self.res_progress["maximum"] = len(items); self.res_progress["value"] = 0
        self.res_start.config(state=tk.DISABLED); self.res_stop_btn.config(state=tk.NORMAL)
        self._set_status(self.res_status, "正在解析...", "blue")
        threading.Thread(target=self._resolve_thread, args=(items,), daemon=True).start()

    def stop_resolve(self):
        self.resolve_stop.set(); self._set_status(self.res_status, "正在停止...", "red")

    def _resolve_thread(self, items):
        for i, d in enumerate(items, 1):
            if self.resolve_stop.is_set(): break
            try:
                ok, bad = resolve_domain(d)
                for ip in ok: self.normal_ip_set.add(ip)
                if ok: self.root.after(0, lambda d=d, ok=ok: self.res_ok.insert(tk.END, f"{d} {' '.join(ok)}\n"))
                if bad: self.root.after(0, lambda d=d, bad=bad: self.res_bad.insert(tk.END, f"{d} {' '.join(bad)}\n"))
            except Exception as e:
                self.root.after(0, lambda d=d, e=e: self.res_err.insert(tk.END, f"{d}: {e}\n"))
            self.root.after(0, lambda i=i: self._res_prog(i))
        self.root.after(0, self._resolve_done)

    def _res_prog(self, i):
        self.res_progress["value"] = i
        self._set_status(self.res_status, f"已完成 {i}/{int(self.res_progress['maximum'])}", "blue")

    def _resolve_done(self):
        self.resolve_running = False
        self.res_start.config(state=tk.NORMAL); self.res_stop_btn.config(state=tk.DISABLED)
        self._set_status(self.res_status, "已停止" if self.resolve_stop.is_set() else "解析完成", "orange" if self.resolve_stop.is_set() else "green")
        if not self.resolve_stop.is_set():
            messagebox.showinfo("完成", "域名解析完成，正常 IP 集合已更新。")

    def export_resolve(self):
        dir_path = filedialog.askdirectory(title="选择结果保存目录")
        if not dir_path: return
        write_text(os.path.join(dir_path, "result.txt"), self.res_ok.get("1.0", tk.END))
        write_text(os.path.join(dir_path, "yichang.txt"), self.res_bad.get("1.0", tk.END))
        write_text(os.path.join(dir_path, "error.txt"), self.res_err.get("1.0", tk.END))
        messagebox.showinfo("导出成功", f"结果已保存到：{dir_path}")

    # ---------------- Match ----------------
    def _tab_match(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="IP/域名匹配")
        ttk.Label(f, text="输入 IP 或域名（每行一个）").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.match_in = scrolledtext.ScrolledText(f, height=8, width=80, font=self.widget_font_big, padx=6, pady=6); self.match_in.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        bf = ttk.Frame(f); bf.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(bf, text="导入文件", command=lambda: self._import_to(self.match_in)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="清除输入", command=lambda: self.match_in.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="加载解析 IP", command=self.load_normal_ips).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="开始匹配", command=self.start_match).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="清空结果", command=lambda: self.match_out.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=3)
        ttk.Label(
            f,
            text="匹配结果说明：域名解析出的 IP 命中「第 1 个标签页已加载的解析 IP」→ 保留域名；未命中这些解析 IP → 输出该域名解析出的 IP。",
        ).pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.match_out = scrolledtext.ScrolledText(f, height=10, width=80, font=self.widget_font_big, padx=6, pady=6); self.match_out.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        bf2 = ttk.Frame(f); bf2.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(bf2, text="导出匹配结果", command=self.export_match).pack(side=tk.LEFT)
        self.match_status = ttk.Label(bf2, text="就绪", foreground="gray"); self.match_status.pack(side=tk.RIGHT, padx=10)

    def load_normal_ips(self):
        if not self.normal_ip_set:
            messagebox.showwarning("无 IP", "请先在「域名解析」标签完成解析。")
            return
        messagebox.showinfo("加载成功", f"已加载 {len(self.normal_ip_set)} 个解析 IP。")

    def start_match(self):
        if not self.normal_ip_set:
            self.load_normal_ips()
            if not self.normal_ip_set: return
        items = lines(self.match_in.get("1.0", tk.END))
        if not items: return messagebox.showwarning("无输入", "请输入 IP 或域名。")
        self.match_out.delete("1.0", tk.END); self._set_status(self.match_status, "正在匹配...", "blue")
        threading.Thread(target=self._match_thread, args=(items,), daemon=True).start()

    def _match_thread(self, items):
        domain_map = {}
        ip_first = {}
        all_domain_ips = set()
        for item in items:
            if is_ip_string(item): continue
            try:
                ok, _ = resolve_domain(item)
                if not ok: continue
                domain_map[item] = ok
                for ip in ok:
                    all_domain_ips.add(ip)
                    ip_first.setdefault(ip, item)
            except Exception:
                pass
        res = []
        for item in items:
            if is_ip_string(item):
                if item not in all_domain_ips: res.append(item)
                continue
            if item not in domain_map: continue
            ok = domain_map[item]
            if not all(ip_first.get(ip) == item for ip in ok): continue
            if any(ip in self.normal_ip_set for ip in ok):
                res.append(item)
            else:
                res.extend(ok)
        self.root.after(0, lambda: self._match_done("\n".join(res)))

    def _match_done(self, text):
        self.match_out.delete("1.0", tk.END); self.match_out.insert(tk.END, text)
        if text: self.match_out.insert(tk.END, "\n")
        self._set_status(self.match_status, f"完成，共 {len(text.splitlines()) if text else 0} 条", "green")

    def export_match(self):
        dir_path = filedialog.askdirectory(title="选择保存目录")
        if not dir_path: return
        write_text(os.path.join(dir_path, "match_result.txt"), self.match_out.get("1.0", tk.END))
        messagebox.showinfo("导出成功", f"匹配结果已保存到：{dir_path}/match_result.txt")

    # ---------------- Scan ----------------
    def _tab_scan(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="端口扫描")
        lf = ttk.LabelFrame(f, text="目标列表（每行一个，支持域名或IP）"); lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        self.scan_in = tk.Text(lf, height=7, wrap=tk.NONE, font=self.widget_font_big, padx=6, pady=6); self.scan_in.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sy = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.scan_in.yview); sy.pack(side=tk.RIGHT, fill=tk.Y); self.scan_in.config(yscrollcommand=sy.set)
        cf = ttk.Frame(f); cf.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(cf, text="端口范围:").pack(side=tk.LEFT)
        self.port_mode = ttk.Combobox(cf, values=["1-65535 全端口", "常用端口 (Web+服务)", "自定义"], state="readonly", width=22)
        self.port_mode.pack(side=tk.LEFT, padx=5); self.port_mode.set("1-65535 全端口"); self.port_mode.bind("<<ComboboxSelected>>", self.on_port_mode_change)
        self.custom_label = ttk.Label(cf, text="自定义端口:"); self.custom_entry = ttk.Entry(cf, width=30); self.custom_entry.insert(0, "80,443,8080")
        ttk.Label(cf, text="线程数:").pack(side=tk.LEFT, padx=(15, 0))
        self.thread_spin = ttk.Spinbox(cf, from_=10, to=500, width=6); self.thread_spin.pack(side=tk.LEFT, padx=5); self.thread_spin.set(DEFAULT_THREADS)
        bf = ttk.Frame(f); bf.pack(fill=tk.X, padx=10, pady=5)
        self.scan_start = ttk.Button(bf, text="开始扫描", command=self.start_scan); self.scan_start.pack(side=tk.LEFT, padx=5)
        self.scan_stop_btn = ttk.Button(bf, text="停止", command=self.stop_scan, state=tk.DISABLED); self.scan_stop_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="清空结果", command=self.clear_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="导出结果", command=self.export_scan).pack(side=tk.LEFT, padx=5)
        self.scan_progress = ttk.Progressbar(f, length=400, mode="determinate"); self.scan_progress.pack(fill=tk.X, padx=10, pady=(0, 5))
        rf = ttk.LabelFrame(f, text="扫描结果"); rf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        cont = ttk.Panedwindow(rf, orient=tk.HORIZONTAL); cont.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(cont)
        cols = ("target", "ip", "port", "status", "code", "banner")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=12)
        for c, t in [
            ("target", "目标"),
            ("ip", "IP地址"),
            ("port", "端口"),
            ("status", "状态"),
            ("code", "状态码"),
            ("banner", "服务信息 (Banner/标题/Server)"),
        ]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=150, anchor=tk.W if c in ("target", "ip", "banner") else tk.CENTER, stretch=True)
        sy = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview); self.tree.config(yscrollcommand=sy.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sy.pack(side=tk.RIGHT, fill=tk.Y)
        right = ttk.LabelFrame(cont, text="Web 列表", width=420)
        right.pack_propagate(False)
        self.web_list = tk.Listbox(right, width=50, height=20, font=self.widget_font_big, selectmode=tk.EXTENDED)
        self.web_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy2 = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.web_list.yview); sy2.pack(side=tk.RIGHT, fill=tk.Y); self.web_list.config(yscrollcommand=sy2.set)
        cont.add(left, weight=7)
        cont.add(right, weight=3)
        wb = ttk.Frame(f); wb.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(wb, text="复制选中 Web", command=self.copy_selected_web).pack(side=tk.LEFT, padx=3)
        ttk.Button(wb, text="复制全部 Web", command=self.copy_all_web).pack(side=tk.LEFT, padx=3)
        ttk.Button(wb, text="清空 Web 列表", command=self.clear_web_list).pack(side=tk.LEFT, padx=3)
        ttk.Button(wb, text="发送选中到 Web 列表", command=self.send_selected_web_auto).pack(side=tk.LEFT, padx=10)
        self.scan_status = ttk.Label(wb, text="就绪", foreground="gray"); self.scan_status.pack(side=tk.RIGHT, padx=10)
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="发送到 Web 列表（自动）", command=self.send_selected_web_auto)
        self.menu.add_command(label="发送到 Web 列表（http）", command=lambda: self.send_selected_web("http"))
        self.menu.add_command(label="发送到 Web 列表（https）", command=lambda: self.send_selected_web("https"))
        self.menu.add_separator()
        self.menu.add_command(label="复制 Web URL", command=self.copy_selected_web)
        self.tree.bind("<Button-3>", self.show_menu)

    def on_port_mode_change(self, _=None):
        if self.port_mode.get() == "自定义":
            self.custom_label.pack(side=tk.LEFT, padx=(15, 0)); self.custom_entry.pack(side=tk.LEFT, padx=5)
        else:
            self.custom_label.pack_forget(); self.custom_entry.pack_forget()

    def parse_ports(self):
        mode = self.port_mode.get()
        if mode == "1-65535 全端口": return list(range(1, 65536))
        if mode == "常用端口 (Web+服务)": return COMMON_PORTS[:]
        ps = []
        seen = set()
        for tok in re.split(r"[\s,]+", self.custom_entry.get().strip()):
            if not tok: continue
            try:
                if "-" in tok:
                    a, b = tok.split("-", 1); a, b = int(a), int(b)
                    if a > b: a, b = b, a
                    rng = range(a, b + 1)
                else:
                    rng = [int(tok)]
            except Exception:
                return None
            for p in rng:
                if 1 <= p <= 65535 and p not in seen:
                    seen.add(p); ps.append(p)
        return ps or None

    def start_scan(self):
        if self.scan_running: return
        raw = lines(self.scan_in.get("1.0", tk.END))
        if not raw: return messagebox.showwarning("警告", "请输入至少一个目标")
        ports = self.parse_ports()
        if ports is None: return messagebox.showerror("错误", "端口格式错误")
        try: th = int(self.thread_spin.get())
        except Exception: th = DEFAULT_THREADS
        th = max(1, min(th, 500))
        self.clear_results(); self.web_set.clear(); self.web_list.delete(0, tk.END)
        self.scan_stop.clear(); self.scan_running = True; self.scan_total = 0; self.scan_done = 0
        self.scan_progress["value"] = 0
        self.scan_start.config(state=tk.DISABLED); self.scan_stop_btn.config(state=tk.NORMAL)
        self._set_status(self.scan_status, "正在解析目标...", "blue")
        threading.Thread(target=self._scan_thread, args=(raw, ports, th), daemon=True).start()

    def stop_scan(self):
        self.scan_stop.set(); self._set_status(self.scan_status, "正在停止...", "red")

    def clear_results(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.scan_results.clear()

    def export_scan(self):
        if not self.tree.get_children(): return messagebox.showwarning("提示", "当前没有可导出的结果。")
        path = filedialog.asksaveasfilename(title="导出结果", defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All", "*.*")], initialfile="scan_result.txt")
        if not path: return
        rows = ["目标\tIP地址\t端口\t状态\t状态码\t服务信息"]
        for iid in self.tree.get_children():
            rows.append("\t".join(map(str, self.tree.item(iid, "values"))))
        write_text(path, "\n".join(rows) + "\n")
        messagebox.showinfo("导出成功", f"结果已保存到：{path}")

    def show_menu(self, event):
        rid = self.tree.identify_row(event.y)
        if rid:
            self.tree.selection_set(rid)
            try: self.menu.tk_popup(event.x_root, event.y_root)
            finally: self.menu.grab_release()

    def _scan_thread(self, targets, ports, th):
        resolved = []
        for t in targets:
            if self.scan_stop.is_set(): break
            name, ips = resolve_target(t)
            if ips: resolved.append((name, ips))
        if not resolved:
            self.root.after(0, lambda: self._scan_done_ui("无可扫描目标")); return
        self.scan_total = sum(len(ips) * len(ports) for _, ips in resolved)
        self.root.after(0, lambda: self._scan_prepare(self.scan_total))
        q = queue.Queue(maxsize=max(th * 4, 200))
        workers = [threading.Thread(target=self._scan_worker, args=(q,), daemon=True) for _ in range(th)]
        for w in workers: w.start()
        for name, ips in resolved:
            for ip in ips:
                for port in ports:
                    if self.scan_stop.is_set(): break
                    while not self.scan_stop.is_set():
                        try:
                            q.put((name, ip, port), timeout=0.2)
                            break
                        except queue.Full:
                            pass
                if self.scan_stop.is_set(): break
            if self.scan_stop.is_set(): break
        for _ in workers:
            while True:
                try:
                    q.put(None, timeout=0.2); break
                except queue.Full:
                    pass
        for w in workers: w.join()
        self.root.after(0, lambda: self._scan_done_ui("已停止" if self.scan_stop.is_set() else "扫描完成"))

    def _scan_prepare(self, total):
        self.scan_progress["maximum"] = total
        self.scan_progress["value"] = 0
        self._set_status(self.scan_status, f"任务数: {total}", "blue")

    def _scan_worker(self, q):
        while True:
            try: task = q.get(timeout=0.5)
            except queue.Empty: continue
            if task is None:
                q.task_done(); break
            target, ip, port = task
            try:
                if not self.scan_stop.is_set():
                    result = self._single_scan(target, ip, port)
                    if result: self.root.after(0, lambda r=result: self._scan_add(r))
            finally:
                self._scan_mark_done()
                q.task_done()

    def _scan_mark_done(self):
        with self.scan_lock:
            self.scan_done += 1
            done, total = self.scan_done, self.scan_total
        if done == total or done % 10 == 0:
            self.root.after(0, lambda: self._scan_prog(done, total))

    def _scan_prog(self, done, total):
        self.scan_progress["value"] = done
        self._set_status(self.scan_status, f"已完成 {done}/{total}", "blue")

    def _single_scan(self, target, ip, port):
        if self.scan_stop.is_set(): return None
        host = target if not is_ip_string(target) else ip
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(1.2)
            if s.connect_ex((ip, port)) != 0:
                return None
        except Exception:
            return None
        finally:
            try: s.close()
            except Exception: pass
        raw, code, title, server = grab_banner(ip, port, self.scan_stop, host)
        info = []
        if title: info.append(f"标题: {title}")
        if server: info.append(f"Server: {server}")
        if raw and not info:
            x = raw.replace("\r", " ").replace("\n", " ")
            info.append(x[:120] + "..." if len(x) > 120 else x)
        return (target, ip, port, "开放", code, " | ".join(info) if info else "无信息")

    def _scan_add(self, result):
        self.tree.insert("", tk.END, values=result)
        self.scan_results.append(result)

    def _scan_done_ui(self, text):
        self.scan_running = False
        self.scan_start.config(state=tk.NORMAL); self.scan_stop_btn.config(state=tk.DISABLED)
        self._set_status(self.scan_status, text, "orange" if text == "已停止" else ("gray" if text.startswith("无可扫描") else "green"))
        if text.startswith("无可扫描"):
            messagebox.showwarning("提示", text)

    def add_web(self, url):
        if url not in self.web_set:
            self.web_set.add(url)
            self.web_list.insert(tk.END, url)

    def send_selected_web_auto(self):
        self.send_selected_web("auto")

    def send_selected_web(self, scheme="auto"):
        sel = self.tree.selection()
        if not sel: return
        n = 0
        for iid in sel:
            target, ip, port, status, code, info = self.tree.item(iid, "values")
            if status != "开放": continue
            try: port = int(port)
            except Exception: continue
            self.add_web(build_web_url(target, ip, port, scheme))
            n += 1
        if n:
            self._set_status(self.scan_status, f"已发送 {n} 条 Web 到右侧列表", "green")

    def copy_selected_web(self):
        sel = self.web_list.curselection()
        if not sel: return
        self._copy_clip("\n".join(self.web_list.get(i) for i in sel))
        self._set_status(self.scan_status, "已复制选中的 Web", "green")

    def copy_all_web(self):
        items = self.web_list.get(0, tk.END)
        if not items: return
        self._copy_clip("\n".join(items))
        self._set_status(self.scan_status, "已复制全部 Web", "green")

    def clear_web_list(self):
        self.web_list.delete(0, tk.END)
        self.web_set.clear()
        self._set_status(self.scan_status, "Web 列表已清空", "gray")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
