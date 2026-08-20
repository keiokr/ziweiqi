# -*- coding: utf-8 -*-
import importlib.util
import json
import os
import queue
import re
import configparser
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk
import tkinter.font as tkfont
from tkinter.scrolledtext import ScrolledText
from urllib.parse import urlsplit
from core.app_icon import apply_app_icon

BASE_DIR = Path(__file__).resolve().parent
ENSCAN_DIR = BASE_DIR / "tools" / "enscan"
ENSCAN_EXE = ENSCAN_DIR / "enscan.exe"
ENSCAN_GOB_FILE = ENSCAN_DIR / "enscan.gob"
ENSCAN_COMPANY_FILE = ENSCAN_DIR / "gongsi.txt"
ENSCAN_XLSX_EXTRACT_SCRIPT = ENSCAN_DIR / "xlsx_extract.py"
ENSCAN_CONFIG_FILE = ENSCAN_DIR / "config.yaml"
PIPELINE_COMPANY_FILE = BASE_DIR / "scanIPAndDomain.txt"
FOFA_CONFIG_FILE = BASE_DIR / "tools" / "FofaMap" / "fofa.ini"
CLEANUP_SCRIPT = BASE_DIR / "core" / "step01_cleanup_last_run.py"
DOMAIN_IP_FILTER_SCRIPT = BASE_DIR / "core" / "domain_ip_url_filter_gui.py"
COMPANY_FULLNAME_FILTER_SCRIPT = BASE_DIR / "core" / "company_fullname_url_filter_gui.py"

PIPELINES = {
    "6": BASE_DIR / "根域名_快_6W子域名_fofa端口.py",
    "6+": BASE_DIR / "根域名_快_6W子域名_4000端口.py",
    "20": BASE_DIR / "根域名_中_20W子域名_4000端口.py",
    "88": BASE_DIR / "根域名_慢_88W子域名_all端口.py",
}
PIPELINE_MODE_LABELS = {
    "6": "6｜快：6W + FOFA端口",
    "6+": "6+｜快：6W + 4000端口",
    "20": "20｜中：20W + 4000端口",
    "88": "88｜慢：88W + 全端口",
}
PIPELINE_LABEL_TO_MODE = {label: mode for mode, label in PIPELINE_MODE_LABELS.items()}


def resolve_pipeline_mode(value: str) -> str | None:
    value = (value or "").strip()
    if value in PIPELINES:
        return value
    return PIPELINE_LABEL_TO_MODE.get(value)

RESULTS_DIR = BASE_DIR / "results"
RAW_RESULT_CSV_NAME = "results2.csv"
RESULT_CSV_GLOB = "*_results2.csv"
ENSCAN_RESULT_XLSX_GLOBS = [
    "gongsi.txt批量查询任务结果*.xlsx",
    "outs/gongsi.txt批量查询任务结果*.xlsx",
]
READ_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16")
HEARTBEAT_SECONDS = 10
POLL_INTERVAL = 0.2
UI_LOG_BATCH_ITEMS = 200
UI_LOG_BATCH_SECONDS = 0.03
LOG_LINE_LIMIT = 5000
AUTO_SAVE_DELAY_MS = 600
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
DOMAIN_RE = re.compile(
    r"(?<![@\w-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?![\w-])"
)
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
COMMON_SECOND_LEVEL_SUFFIXES = {
    "ac",
    "adm",
    "art",
    "asso",
    "co",
    "com",
    "edu",
    "firm",
    "gen",
    "gov",
    "id",
    "ind",
    "inf",
    "mil",
    "name",
    "net",
    "nic",
    "nom",
    "or",
    "org",
    "plc",
    "pro",
    "sch",
}

INVISIBLE_CHARS = "\ufeff\u200b\u200c\u200d\u2060"
_ENSCAN_XLSX_EXTRACTOR = None


def build_help_text() -> str:
    return f"""
GUI 说明： 一键获取目标单位 Web 资产

环境安装：env 目录下一键安装点击 install_env.bat 

1.  配置里面设置fofa和爱企查。

2.  执行方式
     方式1：直接输入 单位全称或备案单位名称一行一个，先执行仅执行enscan，再执行仅执行资产测试。
     方式2：直接输入 根域名和ip列表，在执行仅执行资产测试<方便手动输入根域和ip跑web资产>。

3.  subdomain
    6=快_6W子域名_FOFA 端口集精扫
    6+=快_6W子域名_4000 端口范围精扫
    20=中_20W子域名_4000 端口范围精扫
    88=慢_88W子域名_全端口精扫

4.  单位溯源：   利用FileLocator直接搜索内容当前工具目录就可以溯源到。  
     也可以直接执行完后
     再次点击仅执行enscan停止<无需执行完>
     再次点击仅执行资产测试停止<无需执行完>
     利用FileLocator直接搜索内容backup目录就可以溯源到。

5.  脚本说明
     core/domain_ip_url_filter_gui.py  单独的根域名 / IP URL 保留工具。
     step01_cleanup_last_run.py   清理上次运行遗留结果，先备份再删除，但保留当前靶标和 Enscan XLSX。
     step02_split_targets_domain_ip.py   把输入的“域名和IP列表”拆分成域名目标和 IP 目标。
     step03_prepare_fofa_url.py   整理适合 FOFA 查询使用的目标格式。
     step04_run_fofamap.py   执行 FOFA 查询。
     step05_split_fofa_log.py   整理和拆分 FOFA 结果日志。
     step06_extract_fofa_ports_domains.py 从 FOFA 结果里提取域名和端口。
     step07_extract_fofa_web_urls.py  从 FOFA 结果里提取 Web 地址。
     step08_enum_subdomains_6w.py  子域名枚举，使用 6W 字典，速度快。
     step08_enum_subdomains_20w.py  子域名枚举，使用 20W 字典，平衡速度和覆盖。
     step08_enum_subdomains_88w.py   子域名枚举，使用 88W 字典，覆盖更全但更慢。
     step09_run_oneforall.py   运行 OneForAll 补充子域名。
     step10_run_subfinder.py   运行 subfinder 补充子域名。
     step11_merge_subdomains.py  合并所有子域名结果。
     step12_merge_fofa_domains.py  把 FOFA 里的域名结果继续合并进来。
     step13_keyword_filter_domains.py  按关键词过滤域名，留下更相关的目标。
     step14_import_domains_to_sqlite.py  把域名导入 sqlite 数据库。
     step14_sqlite_utils.py   sqlite 数据库辅助函数<右侧匹配根域名>。
     step15_resolve_domains_to_ip.py  把域名解析成 IP。
     step16_merge_filter_ip.py  合并并过滤 IP 结果（内网/CDN/高防等）。
     step17_run_masscan.py  运行 masscan 进行公网泛端口开放预过滤。
     step18_filter_masscan_ip.py 过滤 masscan 扫描得到的泛端口开放IP，并做最终 IP 校验。
     step19_merge_ports.py  合并并校验各类端口结果。
     step20_run_fscan_port_fofa.py   用 FOFA 相关端口集跑 fscan（公网平衡参数）。
     step20_run_fscan_port_4000.py 用 4000 端口范围跑 fscan（公网平衡参数）。
     step20_run_fscan_port_all.py  用全端口范围跑 fscan（公网平衡参数）。
     step21_extract_fscan_web.py  从 fscan 结果里提取 Web 资产。
     step22_run_webfinder.py   运行 webfinder 做 Web 存活探测。
     step23_extract_webfinder_csv.py  提取 webfinder 的 CSV 结果。
     step24_merge_all_web_sources.py  合并所有 Web 来源结果。
     step25_finalize_live_web.py  整理出最终存活的 Web 资产。
     step26_import_results_csv_to_sqlite.py  把结果 CSV 导入 sqlite。
     step27_deduplicate_sqlite_results.py  对结果做各种去重。
     step28_export_final_results.py  导出最终结果文件。

""".strip()
def decode_output(data: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk", "mbcs"):
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def read_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    for encoding in READ_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def latest_file(base: Path, patterns):
    candidates = []
    for pattern in patterns:
        candidates.extend(base.glob(pattern))
    files = [item for item in candidates if item.is_file()]
    if not files:
        return None
    return max(files, key=lambda item: item.stat().st_mtime)


def child_tool_env(extra=None):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    if extra:
        env.update(extra)
    return env


def strip_invisible_edges(value) -> str:
    if value is None:
        return ""
    translated = str(value).translate({ord(ch): None for ch in INVISIBLE_CHARS})
    return translated.strip()


def get_python_executable() -> str:
    current = Path(sys.executable)
    if current.name.lower() == "pythonw.exe":
        console_python = current.with_name("python.exe")
        if console_python.exists():
            return str(console_python)
    return str(current)


def get_gui_python_executable() -> str:
    current = Path(sys.executable)
    if current.name.lower() == "python.exe":
        gui_python = current.with_name("pythonw.exe")
        if gui_python.exists():
            return str(gui_python)
    return str(current)


def load_enscan_xlsx_extractor():
    global _ENSCAN_XLSX_EXTRACTOR
    if _ENSCAN_XLSX_EXTRACTOR is not None:
        return _ENSCAN_XLSX_EXTRACTOR
    if not ENSCAN_XLSX_EXTRACT_SCRIPT.exists():
        raise FileNotFoundError(f"未找到 Enscan 提取脚本：{ENSCAN_XLSX_EXTRACT_SCRIPT}")
    spec = importlib.util.spec_from_file_location("enscan_xlsx_extract", ENSCAN_XLSX_EXTRACT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载提取脚本：{ENSCAN_XLSX_EXTRACT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _ENSCAN_XLSX_EXTRACTOR = module
    return module


def is_valid_ipv4(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def normalize_target(value: str):
    candidate = strip_invisible_edges(value).strip("\"'[](){}<>;,")
    if not candidate:
        return None
    if "://" in candidate:
        try:
            candidate = urlsplit(candidate).hostname or ""
        except Exception:
            return None
    candidate = candidate.strip().lower().rstrip(".")
    if candidate.startswith("*."):
        candidate = candidate[2:]
    if candidate.startswith("www."):
        candidate = candidate[4:]
    if not candidate or "@" in candidate:
        return None
    if is_valid_ipv4(candidate):
        return candidate
    if DOMAIN_RE.fullmatch(candidate):
        return candidate
    return None


def extract_targets_from_text(text: str):
    targets = []
    seen = set()

    def add(value: str):
        normalized = normalize_target(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            targets.append(normalized)

    stripped = strip_invisible_edges(text)
    if stripped:
        add(stripped)

    for match in URL_RE.findall(text):
        add(match)
    for match in IPV4_RE.findall(text):
        add(match)
    for match in DOMAIN_RE.findall(text):
        add(match)

    return targets


def extract_targets_from_xlsx_file(path: Path):
    try:
        extractor = load_enscan_xlsx_extractor()
        return extractor.extract_targets_from_xlsx_file(path, ENSCAN_COMPANY_FILE, debug=False)
    except Exception as exc:
        raise RuntimeError(f"Enscan XLSX 提取失败: {exc}") from exc


class ZiWeiQiGui(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_app_icon(self, app_id="ziweiqi.desktop.main")
        self.title("资产测绘")
        window_width = 1260
        window_height = 880
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = max(0, (screen_width - window_width) // 2)
        y_pos = max(0, (screen_height - window_height) // 4)
        self.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        self.minsize(1100, 780)

        self.python_executable = get_python_executable()
        self.gui_python_executable = get_gui_python_executable()
        self.log_queue = queue.Queue()
        self.worker = None
        self.stop_event = threading.Event()
        self.current_process = None
        self.current_process_lock = threading.Lock()

        self.mode_var = tk.StringVar(value=PIPELINE_MODE_LABELS["6"])
        self.invest_var = tk.StringVar(value="51")
        self.delay_var = tk.StringVar(value="3")
        self.deep_var = tk.StringVar(value="1")
        self.status_var = tk.StringVar(value="空闲")
        self.xlsx_var = tk.StringVar(value="")
        self.target_var = tk.StringVar(value="")
        self.all_result_csv_var = tk.StringVar(value="")
        self.result_csv_var = tk.StringVar(value="")
        self.fofa_email_var = tk.StringVar(value="")
        self.fofa_key_var = tk.StringVar(value="")
        self.target_autosave_after = None
        self.session_latest_xlsx = None

        self._build_ui()
        self._load_initial_content()
        self._refresh_output_vars()
        self.after(100, self._drain_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_fonts(self):
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
            try:
                current = tkfont.nametofont(name)
                size = current.cget("size")
                if isinstance(size, int):
                    current.configure(size=size + 1 if size > 0 else size - 1)
            except Exception:
                continue

    def _build_ui(self):
        self._configure_fonts()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        style = ttk.Style(self)
        style.configure("Main.TNotebook.Tab", padding=(20, 4), font=("Microsoft YaHei UI", 10))

        notebook = ttk.Notebook(self, style="Main.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew")

        main_page = ttk.Frame(notebook)
        config_page = ttk.Frame(notebook)
        help_page = ttk.Frame(notebook)
        notebook.add(main_page, text="Main")
        notebook.add(config_page, text="配置")
        notebook.add(help_page, text="说明")

        main_page.columnconfigure(0, weight=1)
        main_page.rowconfigure(3, weight=1)
        config_page.columnconfigure(0, weight=1)
        config_page.rowconfigure(0, weight=1)
        help_page.columnconfigure(0, weight=1)
        help_page.rowconfigure(0, weight=1)

        panels = ttk.Frame(main_page, padding=12)
        panels.grid(row=0, column=0, sticky="nsew")
        panels.columnconfigure(0, weight=1, uniform="top_panels")
        panels.columnconfigure(1, weight=1, uniform="top_panels")
        panels.columnconfigure(2, weight=1, uniform="top_panels")
        panels.rowconfigure(0, weight=1)

        company_panel = ttk.LabelFrame(panels, text="单位全称或备案名<1.仅执行enscan>", padding=12)
        company_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        company_panel.columnconfigure(0, weight=1)
        company_panel.rowconfigure(0, weight=1)

        target_panel = ttk.LabelFrame(panels, text="根域名和IP列表<2.仅执行资产测绘>", padding=12)
        target_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        target_panel.columnconfigure(0, weight=1)
        target_panel.rowconfigure(0, weight=1)

        status_panel = ttk.LabelFrame(panels, text="状态", padding=12)
        status_panel.grid(row=0, column=2, sticky="nsew")
        status_panel.columnconfigure(1, weight=1)
        status_panel.rowconfigure(2, weight=1)

        self.company_text = ScrolledText(company_panel, height=10, font=("Consolas", 12))
        self.company_text.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.target_text = ScrolledText(target_panel, height=10, font=("Consolas", 12))
        self.target_text.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.target_text.bind("<<Modified>>", self._on_target_modified)

        company_buttons = ttk.Frame(company_panel)
        company_buttons.grid(row=1, column=0, sticky="w")
        self.save_button = ttk.Button(company_buttons, text="保存名单", command=self.save_company_files_manual)
        self.save_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(company_buttons, text="重新加载名单", command=self._load_company_content).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(company_buttons, text="打开文件目录", command=lambda: self._open_path(ENSCAN_DIR / "outs")).grid(row=0, column=2)

        target_buttons = ttk.Frame(target_panel)
        target_buttons.grid(row=1, column=0, sticky="w")
        self.save_target_button = ttk.Button(target_buttons, text="保存名单", command=self.save_target_file_manual)
        self.save_target_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(target_buttons, text="重新加载名单", command=self._load_target_content).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(target_buttons, text="打开文件目录", command=lambda: self._open_path(BASE_DIR)).grid(row=0, column=2)

        ttk.Label(status_panel, text="运行日志", wraplength=260, justify="left").grid(row=0, column=0, sticky="nw")
        ttk.Label(status_panel, text=str(BASE_DIR), wraplength=260, justify="left").grid(row=0, column=1, sticky="nw", padx=(8, 0))
        ttk.Label(status_panel, text="当前状态").grid(row=1, column=0, sticky="nw", pady=(12, 0))
        ttk.Label(status_panel, textvariable=self.status_var, wraplength=260, justify="left").grid(row=1, column=1, sticky="nw", padx=(8, 0), pady=(12, 0))

        controls = ttk.LabelFrame(main_page, text="执行控制", padding=12)
        controls.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        for index in range(4):
            controls.columnconfigure(index, weight=1, uniform="exec_controls")

        mode_control = ttk.Frame(controls)
        invest_control = ttk.Frame(controls)
        deep_control = ttk.Frame(controls)
        delay_control = ttk.Frame(controls)
        for index, frame in enumerate((mode_control, invest_control, deep_control, delay_control)):
            frame.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            frame.columnconfigure(1, weight=1)

        ttk.Label(mode_control, text="扫描模式").grid(row=0, column=0, sticky="w")
        self.mode_box = ttk.Combobox(
            mode_control,
            textvariable=self.mode_var,
            values=[PIPELINE_MODE_LABELS[mode] for mode in PIPELINES],
            state="readonly",
            width=18,
        )
        self.mode_box.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(invest_control, text="控股（默认51）").grid(row=0, column=0, sticky="w")
        ttk.Entry(invest_control, textvariable=self.invest_var, width=8).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(deep_control, text="1子公司/2孙公司").grid(row=0, column=0, sticky="w")
        ttk.Entry(deep_control, textvariable=self.deep_var, width=8).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(delay_control, text="超时").grid(row=0, column=0, sticky="w")
        ttk.Entry(delay_control, textvariable=self.delay_var, width=8).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        actions = ttk.Frame(main_page, padding=(12, 0, 12, 12))
        actions.grid(row=2, column=0, sticky="ew")
        self.run_enscan_button = ttk.Button(actions, text="仅执行1", command=self.run_enscan)
        self.run_enscan_button.grid(row=0, column=0, padx=(0, 8))
        self.run_pipeline_button = ttk.Button(actions, text="仅执行2", command=self.run_pipeline)
        self.run_pipeline_button.grid(row=0, column=1, padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="Stop", command=self.stop_current_task, state="disabled")
        self.stop_button.grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="目标全称提取/去除已出局", command=self._open_company_fullname_filter_tool).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(actions, text="备案资产提取/去除已出局", command=self._open_domain_ip_filter_tool).grid(row=0, column=4, padx=(0, 8))
        bottom_panels = ttk.Frame(main_page, padding=(12, 0, 12, 12))
        bottom_panels.grid(row=3, column=0, sticky="nsew")
        bottom_panels.columnconfigure(0, weight=1, uniform="bottom_panels")
        bottom_panels.columnconfigure(1, weight=1, uniform="bottom_panels")
        bottom_panels.rowconfigure(0, weight=1)

        logs = ttk.LabelFrame(bottom_panels, text="运行日志", padding=12)
        logs.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        logs.columnconfigure(0, weight=1)
        logs.rowconfigure(0, weight=1)
        self.log_text = ScrolledText(logs, height=18, font=("Consolas", 11), state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        outputs = ttk.LabelFrame(bottom_panels, text="输出文件", padding=12)
        outputs.grid(row=0, column=1, sticky="nsew")
        outputs.columnconfigure(1, weight=1)

        ttk.Label(outputs, text="当前靶标 TXT").grid(row=0, column=0, sticky="w")
        ttk.Entry(outputs, textvariable=self.target_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(outputs, text="Open", command=lambda: self._open_var_path(self.target_var)).grid(row=0, column=2)

        ttk.Label(outputs, text="当前 Enscan XLSX").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(outputs, textvariable=self.xlsx_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(outputs, text="Open", command=lambda: self._open_var_path(self.xlsx_var)).grid(row=1, column=2, pady=(8, 0))

        ttk.Label(outputs, text="未去重所有资产 CSV").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(outputs, textvariable=self.all_result_csv_var).grid(row=2, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(outputs, text="Open", command=lambda: self._open_var_path(self.all_result_csv_var)).grid(row=2, column=2, pady=(8, 0))

        ttk.Label(outputs, text="去重后资产 CSV").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(outputs, textvariable=self.result_csv_var).grid(row=3, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(outputs, text="Open", command=lambda: self._open_var_path(self.result_csv_var)).grid(row=3, column=2, pady=(8, 0))

        config_body = ttk.Frame(config_page, padding=(12, 0, 12, 12))
        config_body.grid(row=0, column=0, sticky="nsew")
        config_body.columnconfigure(0, weight=1)
        config_body.columnconfigure(1, weight=1)
        config_body.rowconfigure(0, weight=1)

        fofa_frame = ttk.LabelFrame(config_body, text="FOFA配置", padding=12)
        fofa_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        fofa_frame.columnconfigure(1, weight=1)
        ttk.Label(fofa_frame, text="FOFA邮箱").grid(row=0, column=0, sticky="w")
        ttk.Entry(fofa_frame, textvariable=self.fofa_email_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(fofa_frame, text="FOFA Key").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(fofa_frame, textvariable=self.fofa_key_var).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))
        config_actions = ttk.Frame(fofa_frame)
        config_actions.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.save_config_button = ttk.Button(config_actions, text="保存配置", command=self.save_config_files)
        self.save_config_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(config_actions, text="重新加载配置", command=self._load_config_content).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(config_actions, text="打开FOFA配置", command=lambda: self._open_path(FOFA_CONFIG_FILE)).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(config_actions, text="打开Enscan配置", command=lambda: self._open_path(ENSCAN_CONFIG_FILE)).grid(row=0, column=3)

        aiqicha_frame = ttk.LabelFrame(config_body, text="爱企查Cookie", padding=12)
        aiqicha_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        aiqicha_frame.columnconfigure(0, weight=1)
        aiqicha_frame.rowconfigure(0, weight=1)
        self.aiqicha_cookie_text = ScrolledText(aiqicha_frame, height=16, font=("Consolas", 11))
        self.aiqicha_cookie_text.grid(row=0, column=0, sticky="nsew")

        help_frame = ttk.LabelFrame(help_page, text="说明", padding=12)
        help_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        help_frame.columnconfigure(0, weight=1)
        help_frame.rowconfigure(0, weight=1)
        self.help_text = ScrolledText(help_frame, wrap="word", font=("Microsoft YaHei UI", 11))
        self.help_text.grid(row=0, column=0, sticky="nsew")
        self.help_text.insert("1.0", build_help_text() + "\n")
        self.help_text.configure(state="disabled")

        self.action_buttons = [
            self.save_button,
            self.save_target_button,
            self.save_config_button,
            self.run_enscan_button,
            self.run_pipeline_button,
        ]

    def _load_initial_content(self):
        self._load_company_content()
        self._load_target_content()
        self._load_config_content()

    def _load_company_content(self):
        content = read_text_file(ENSCAN_COMPANY_FILE)
        self.company_text.delete("1.0", tk.END)
        if content:
            self.company_text.insert("1.0", content)
        self.company_text.edit_modified(False)

    def _load_target_content(self):
        content = read_text_file(PIPELINE_COMPANY_FILE)
        self.target_text.delete("1.0", tk.END)
        lines = extract_targets_from_text(content) if content else []
        if lines:
            self.target_text.insert("1.0", "\n".join(lines) + "\n")
            self._write_target_file(lines)
        self.target_text.edit_modified(False)

    def _load_config_content(self):
        self._load_fofa_config()
        self._load_aiqicha_cookie()

    def _load_fofa_config(self):
        parser = configparser.ConfigParser()
        if FOFA_CONFIG_FILE.exists():
            content = read_text_file(FOFA_CONFIG_FILE)
            if content.strip():
                parser.read_string(content)
        self.fofa_email_var.set(strip_invisible_edges(parser.get("userinfo", "email", fallback="")))
        self.fofa_key_var.set(strip_invisible_edges(parser.get("userinfo", "key", fallback="")))

    def _read_aiqicha_cookie_value(self):
        content = read_text_file(ENSCAN_CONFIG_FILE)
        match = re.search(r"(?m)^\s*aiqicha:\s*'(.*)'\s*(?:#.*)?$", content)
        if match:
            return strip_invisible_edges(match.group(1).replace("''", "'"))
        match = re.search(r'(?m)^\s*aiqicha:\s*"(.*)"\s*(?:#.*)?$', content)
        if match:
            return strip_invisible_edges(match.group(1))
        return ""

    def _load_aiqicha_cookie(self):
        content = self._read_aiqicha_cookie_value()
        self.aiqicha_cookie_text.delete("1.0", tk.END)
        if content:
            self.aiqicha_cookie_text.insert("1.0", content)

    def _write_fofa_config(self, email: str, key: str):
        email = strip_invisible_edges(email)
        key = strip_invisible_edges(key)
        content = read_text_file(FOFA_CONFIG_FILE)
        if not content.strip():
            content = "[userinfo]\nemail = \nkey = \n"
        if "[userinfo]" not in content:
            content = "[userinfo]\nemail = \nkey = \n\n" + content

        if re.search(r"(?m)^email\s*=", content):
            content = re.sub(r"(?m)^(email\s*=\s*).*$", rf"\1{email}", content, count=1)
        else:
            content = content.replace("[userinfo]\n", f"[userinfo]\nemail = {email}\n", 1)

        if re.search(r"(?m)^key\s*=", content):
            content = re.sub(r"(?m)^(key\s*=\s*).*$", rf"\1{key}", content, count=1)
        else:
            content = content.replace("[userinfo]\n", f"[userinfo]\nkey = {key}\n", 1)

        FOFA_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        FOFA_CONFIG_FILE.write_text(content, encoding="utf-8")

    def _write_aiqicha_cookie(self, cookie: str):
        cookie = strip_invisible_edges(cookie)
        content = read_text_file(ENSCAN_CONFIG_FILE)
        escaped = cookie.replace("'", "''")
        line = f"  aiqicha: '{escaped}'        # 爱企查 Cookie"

        if re.search(r"(?m)^\s*aiqicha:.*$", content):
            content = re.sub(r"(?m)^\s*aiqicha:.*$", line, content, count=1)
        elif "cookies:\n" in content:
            content = content.replace("cookies:\n", "cookies:\n" + line + "\n", 1)
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            content += "cookies:\n" + line + "\n"

        ENSCAN_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENSCAN_CONFIG_FILE.write_text(content, encoding="utf-8")

    def save_config_files(self):
        email = strip_invisible_edges(self.fofa_email_var.get())
        key = strip_invisible_edges(self.fofa_key_var.get())
        cookie = strip_invisible_edges(self.aiqicha_cookie_text.get("1.0", tk.END))
        try:
            self.fofa_email_var.set(email)
            self.fofa_key_var.set(key)
            self.aiqicha_cookie_text.delete("1.0", tk.END)
            if cookie:
                self.aiqicha_cookie_text.insert("1.0", cookie)
            self._write_fofa_config(email, key)
            self._write_aiqicha_cookie(cookie)
            self._append_log(
                f"已保存 FOFA 配置：{FOFA_CONFIG_FILE}\n"
                f"已保存 Enscan Cookie 配置：{ENSCAN_CONFIG_FILE}\n"
            )
            messagebox.showinfo("完成", "配置保存成功。")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def _append_log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message)
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > LOG_LINE_LIMIT:
            self.log_text.delete("1.0", f"{line_count - LOG_LINE_LIMIT}.0")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _drain_log_queue(self):
        logs = []
        latest_status = None
        need_refresh_outputs = False
        done_payload = None
        processed = 0
        started_at = time.monotonic()

        try:
            while processed < UI_LOG_BATCH_ITEMS and time.monotonic() - started_at < UI_LOG_BATCH_SECONDS:
                kind, payload = self.log_queue.get_nowait()
                processed += 1
                if kind == "log":
                    logs.append(payload)
                elif kind == "status":
                    latest_status = payload
                elif kind == "refresh_outputs":
                    need_refresh_outputs = True
                elif kind == "done":
                    done_payload = payload
        except queue.Empty:
            pass

        if logs:
            self._append_log("".join(logs))
        if latest_status is not None:
            self.status_var.set(latest_status)
        if need_refresh_outputs:
            self._refresh_output_vars()
        if done_payload is not None:
            self._set_running(False)
            ok, message = done_payload
            self.status_var.set(message)
            if ok:
                messagebox.showinfo("完成", message)
            else:
                messagebox.showerror("错误", message)

        delay = 10 if not self.log_queue.empty() else 100
        self.after(delay, self._drain_log_queue)

    def _set_running(self, running: bool):
        action_state = "disabled" if running else "normal"
        for button in self.action_buttons:
            button.configure(state=action_state)
        self.stop_button.configure(state="normal" if running else "disabled")
        if not running:
            self.worker = None
            self.stop_event.clear()
            with self.current_process_lock:
                self.current_process = None

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("任务仍在运行", "当前还有任务在执行，是否关闭窗口并停止任务？"):
                return
        self.destroy()

    def _open_path(self, path: Path):
        target = Path(path)
        if not target.exists():
            messagebox.showwarning("路径不存在", f"找不到路径：{target}")
            return
        os.startfile(str(target))

    def _open_var_path(self, variable: tk.StringVar):
        value = variable.get().strip()
        if not value:
            messagebox.showwarning("打开失败", "无法打开指定路径。")
            return
        self._open_path(Path(value))

    def _open_domain_ip_filter_tool(self):
        if not DOMAIN_IP_FILTER_SCRIPT.exists():
            messagebox.showerror("启动失败", f"未找到工具：{DOMAIN_IP_FILTER_SCRIPT}")
            return
        latest_result_txt = latest_file(RESULTS_DIR, ["*资产已去重_*.txt", "*_results2.txt"])
        result_file = BASE_DIR / "tools" / "domaintoIP" / "result.txt"
        subprocess.Popen(
            [self.gui_python_executable, str(DOMAIN_IP_FILTER_SCRIPT)],
            cwd=str(BASE_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=child_tool_env({
                "ZIWEIQI_RESULT_FILE": str(result_file),
                "ZIWEIQI_URL_FILE": str(latest_result_txt) if latest_result_txt else "",
                "ZIWEIQI_OUTPUT_DIR": str(BASE_DIR),
            }),
        )

    def _open_company_fullname_filter_tool(self):
        if not COMPANY_FULLNAME_FILTER_SCRIPT.exists():
            messagebox.showerror("启动失败", f"未找到工具：{COMPANY_FULLNAME_FILTER_SCRIPT}")
            return
        latest_result_txt = latest_file(RESULTS_DIR, ["*资产已去重_*.txt", "*_results2.txt"])
        latest_xlsx = None
        if self.session_latest_xlsx and Path(self.session_latest_xlsx).exists():
            latest_xlsx = Path(self.session_latest_xlsx)
        else:
            latest_xlsx = latest_file(ENSCAN_DIR, ENSCAN_RESULT_XLSX_GLOBS)
        result_file = BASE_DIR / "tools" / "domaintoIP" / "result.txt"
        subprocess.Popen(
            [self.gui_python_executable, str(COMPANY_FULLNAME_FILTER_SCRIPT)],
            cwd=str(BASE_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=child_tool_env({
                "ZIWEIQI_XLSX_FILE": str(latest_xlsx) if latest_xlsx else "",
                "ZIWEIQI_RESULT_FILE": str(result_file),
                "ZIWEIQI_URL_FILE": str(latest_result_txt) if latest_result_txt else "",
                "ZIWEIQI_OUTPUT_DIR": str(BASE_DIR),
            }),
        )

    def _kill_enscan_processes(self):
        try:
            subprocess.run(
                ["taskkill", "/IM", "enscan.exe", "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    def _remove_enscan_gob(self):
        if not ENSCAN_GOB_FILE.exists():
            self._append_log(f"[INFO] 未发现：{ENSCAN_GOB_FILE}\n")
            return

        last_error = None
        for _ in range(10):
            try:
                ENSCAN_GOB_FILE.unlink()
                self._append_log(f"[INFO] 已删除：{ENSCAN_GOB_FILE}\n")
                return
            except FileNotFoundError:
                self._append_log(f"[INFO] 未发现：{ENSCAN_GOB_FILE}\n")
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.2)
            except Exception as exc:
                raise RuntimeError(f"删除 Enscan 缓存失败：{exc}") from exc

        raise RuntimeError(f"删除 Enscan 缓存失败：{last_error}")

    def _prepare_enscan_run(self):
        self._append_log("[INFO] 准备 Enscan：先结束 enscan 进程并清理 gob 缓存\n")
        self._kill_enscan_processes()
        self._remove_enscan_gob()

    def _refresh_output_vars(self):
        raw_csv = RESULTS_DIR / RAW_RESULT_CSV_NAME
        latest_csv = latest_file(RESULTS_DIR, [RESULT_CSV_GLOB])
        latest_xlsx = None
        if self.session_latest_xlsx and Path(self.session_latest_xlsx).exists():
            latest_xlsx = Path(self.session_latest_xlsx)
        else:
            self.session_latest_xlsx = None
        self.xlsx_var.set(str(latest_xlsx) if latest_xlsx else "")
        self.target_var.set(str(PIPELINE_COMPANY_FILE) if PIPELINE_COMPANY_FILE.exists() else "")
        self.all_result_csv_var.set(str(raw_csv) if raw_csv.exists() else "")
        self.result_csv_var.set(str(latest_csv) if latest_csv else "")
        if PIPELINE_COMPANY_FILE.exists():
            self._load_target_content()

    def _clear_xlsx_output(self):
        self.session_latest_xlsx = None
        self.xlsx_var.set("")

    def _get_company_lines(self):
        raw = self.company_text.get("1.0", tk.END)
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            raise ValueError("公司名单不能为空。")
        return lines

    def _clear_company_lines_and_file(self, log_message: bool = False):
        self.company_text.delete("1.0", tk.END)
        self.company_text.edit_modified(False)
        ENSCAN_DIR.mkdir(parents=True, exist_ok=True)
        ENSCAN_COMPANY_FILE.write_text("", encoding="utf-8")
        if log_message:
            self._append_log(f"已清空单位全称或备案名：{ENSCAN_COMPANY_FILE}\n")

    def _get_target_lines(self):
        raw = self.target_text.get("1.0", tk.END)
        lines = extract_targets_from_text(raw)
        if not lines:
            raise ValueError("根域名和IP列表不能为空，且只支持根域名或IP。")
        return lines

    def _set_target_lines(self, lines):
        content = ("\n".join(lines) + "\n") if lines else ""
        current = self.target_text.get("1.0", tk.END)
        if current != content:
            self.target_text.delete("1.0", tk.END)
            if content:
                self.target_text.insert("1.0", content)
        self.target_text.edit_modified(False)

    def _clear_target_lines_and_file(self, log_message: bool = False):
        if self.target_autosave_after is not None:
            self.after_cancel(self.target_autosave_after)
            self.target_autosave_after = None
        self._set_target_lines([])
        PIPELINE_COMPANY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PIPELINE_COMPANY_FILE.write_text("", encoding="utf-8")
        self.target_var.set(str(PIPELINE_COMPANY_FILE))
        if log_message:
            self._append_log(f"已清空根域名和IP列表：{PIPELINE_COMPANY_FILE}\n")

    def save_company_files(self, clear_target: bool = False):
        try:
            lines = self._get_company_lines()
        except ValueError as exc:
            messagebox.showwarning("输入不完整", str(exc))
            return False
        self._write_company_files(lines)
        if clear_target:
            self._clear_target_lines_and_file(log_message=True)
        return True

    def save_company_files_manual(self):
        return self.save_company_files(clear_target=True)

    def _write_company_files(self, lines):
        ENSCAN_DIR.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines) + "\n"
        ENSCAN_COMPANY_FILE.write_text(content, encoding="utf-8")
        self._append_log(f"已保存公司名单：{ENSCAN_COMPANY_FILE}\n")

    def save_target_file(self, clear_company: bool = False):
        try:
            lines = self._get_target_lines()
        except ValueError as exc:
            messagebox.showwarning("输入不完整", str(exc))
            return False
        self._set_target_lines(lines)
        self._write_target_file(lines, log_message=True)
        if clear_company:
            self._clear_company_lines_and_file(log_message=True)
        return True

    def save_target_file_manual(self):
        return self.save_target_file(clear_company=True)

    def _write_target_file(self, lines, log_message: bool = False):
        PIPELINE_COMPANY_FILE.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines) + "\n"
        PIPELINE_COMPANY_FILE.write_text(content, encoding="utf-8")
        self.target_var.set(str(PIPELINE_COMPANY_FILE))
        if log_message:
            self._append_log(f"已保存域名和IP列表：{PIPELINE_COMPANY_FILE}\n")

    def _autosave_target_file(self):
        self.target_autosave_after = None
        raw = self.target_text.get("1.0", tk.END)
        lines = extract_targets_from_text(raw)
        content = ("\n".join(lines) + "\n") if lines else ""
        PIPELINE_COMPANY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PIPELINE_COMPANY_FILE.write_text(content, encoding="utf-8")
        self._set_target_lines(lines)
        self.target_var.set(str(PIPELINE_COMPANY_FILE) if PIPELINE_COMPANY_FILE.exists() else "")

    def _on_target_modified(self, _event=None):
        if not self.target_text.edit_modified():
            return
        self.target_text.edit_modified(False)
        if self.target_autosave_after is not None:
            self.after_cancel(self.target_autosave_after)
        self.target_autosave_after = self.after(AUTO_SAVE_DELAY_MS, self._autosave_target_file)

    def _extract_targets_to_pipeline_file(self, xlsx_path: Path):
        targets = extract_targets_from_xlsx_file(xlsx_path)
        if not targets:
            raise RuntimeError(f"Enscan 执行完成，但未能从 {xlsx_path} 第二个 sheet 中按单位名称匹配后提取到有效根域名")
        PIPELINE_COMPANY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PIPELINE_COMPANY_FILE.write_text("\n".join(targets) + "\n", encoding="utf-8")
        return targets

    def _sync_targets_from_xlsx(self, xlsx_path: Path):
        targets = self._extract_targets_to_pipeline_file(xlsx_path)
        self.session_latest_xlsx = xlsx_path
        self._set_target_lines(targets)
        self.target_var.set(str(PIPELINE_COMPANY_FILE))
        self.log_queue.put((
            "log",
            f"\n已从 XLSX 生成靶标文件：{PIPELINE_COMPANY_FILE}\n来源：{xlsx_path}\n提取数量：{len(targets)}\n",
        ))
        self.log_queue.put(("refresh_outputs", None))
        return targets

    def _sync_targets_from_xlsx_for_worker(self, xlsx_path: Path):
        targets = self._extract_targets_to_pipeline_file(xlsx_path)
        self.session_latest_xlsx = xlsx_path
        self.log_queue.put((
            "log",
            f"\n已自动从 Enscan XLSX 生成靶标文件：{PIPELINE_COMPANY_FILE}\n来源：{xlsx_path}\n提取数量：{len(targets)}\n",
        ))
        self.log_queue.put(("refresh_outputs", None))
        return targets

    def sync_targets_from_latest_xlsx(self):
        try:
            latest_xlsx = latest_file(ENSCAN_DIR, ENSCAN_RESULT_XLSX_GLOBS)
            if not latest_xlsx:
                raise FileNotFoundError("未找到 Enscan XLSX")
            self._sync_targets_from_xlsx(latest_xlsx)
            messagebox.showinfo("完成", f"已根据最新 XLSX 生成 {PIPELINE_COMPANY_FILE.name}")
        except Exception as exc:
            messagebox.showerror("生成失败", str(exc))

    def _validate_number(self, value: str, name: str, allow_zero: bool = False) -> int:
        value = value.strip()
        if not value.isdigit():
            raise ValueError(f"参数 {name} 必须是整数。")
        number = int(value)
        if allow_zero:
            if number < 0:
                raise ValueError(f"参数 {name} 不能小于 0。")
        elif number <= 0:
            raise ValueError(f"参数 {name} 必须大于 0。")
        return number

    def _archive_existing_enscan_xlsx(self):
        xlsx_files = []
        for pattern in ENSCAN_RESULT_XLSX_GLOBS:
            xlsx_files.extend(path for path in ENSCAN_DIR.glob(pattern) if path.is_file())
        if not xlsx_files:
            return
        backup_dir = BASE_DIR / "backup" / time.strftime("enscan_xlsx_%Y%m%d_%H%M%S") / "xlsx"
        moved = []
        for path in sorted(set(xlsx_files)):
            try:
                relative = path.relative_to(ENSCAN_DIR)
            except ValueError:
                relative = Path(path.name)
            target = backup_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}_{int(time.time())}{target.suffix}")
            shutil.move(str(path), str(target))
            moved.append(target)
        if moved:
            self._append_log(f"[INFO] 已归档旧 Enscan XLSX 到：{backup_dir}\n")

    def _build_job_snapshot(self, include_enscan: bool, include_pipeline: bool):
        if not include_enscan and not include_pipeline:
            raise ValueError("请至少选择一个执行阶段。")

        steps = []

        if include_enscan:
            self._prepare_enscan_run()
            self._archive_existing_enscan_xlsx()

        if include_pipeline and CLEANUP_SCRIPT.exists():
            steps.append({
                "name": "清理上次运行结果",
                "command": [self.python_executable, str(CLEANUP_SCRIPT)],
                "cwd": BASE_DIR,
                "kind": "cleanup",
            })

        if include_enscan:
            if not ENSCAN_EXE.exists():
                raise FileNotFoundError(f"未找到 Enscan 程序：{ENSCAN_EXE}")
            invest = self._validate_number(self.invest_var.get(), "控股")
            delay = self._validate_number(self.delay_var.get(), "超时")
            deep = self._validate_number(self.deep_var.get(), "深度")
            if not self.save_company_files():
                raise ValueError("保存名单失败。")
            steps.append({
                "name": "Enscan",
                "command": [
                    str(ENSCAN_EXE),
                    "-invest", str(invest),
                    "-f", ENSCAN_COMPANY_FILE.name,
                    "-delay", str(delay),
                    "-type", "aqc",
                    "-deep", str(deep),
                ],
                "cwd": ENSCAN_DIR,
                "kind": "enscan",
            })

        if include_pipeline:
            selected_mode = resolve_pipeline_mode(self.mode_var.get())
            script = PIPELINES.get(selected_mode)
            if script is None:
                raise ValueError("请选择有效的资产测绘模式。")
            if not script.exists():
                raise FileNotFoundError(f"未找到资产测绘脚本：{script}")
            if not self.save_target_file():
                raise ValueError("保存域名和IP列表失败。")
            steps.append({
                "name": f"资产测绘模式 {PIPELINE_MODE_LABELS.get(selected_mode, selected_mode)}",
                "command": [self.python_executable, str(script)],
                "cwd": BASE_DIR,
                "kind": "pipeline",
            })

        return {
            "steps": steps,
        }

    def _start_worker(self, title: str, snapshot):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("任务进行中", "请等待当前任务执行完成。")
            return
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self._append_log(f"[INFO] 开始执行：{title}\n")
        self.status_var.set(f"正在准备：{title}")
        self._set_running(True)
        self.worker = threading.Thread(target=self._worker_wrapper, args=(title, snapshot), daemon=True)
        self.worker.start()

    def _worker_wrapper(self, title: str, snapshot):
        try:
            for step in snapshot["steps"]:
                self._run_process(step["name"], step["command"], Path(step["cwd"]))
                if step.get("kind") == "enscan":
                    latest_xlsx = latest_file(ENSCAN_DIR, ENSCAN_RESULT_XLSX_GLOBS)
                    if not latest_xlsx:
                        raise FileNotFoundError("Enscan 执行完成，但未找到结果 XLSX")
                    self._sync_targets_from_xlsx_for_worker(latest_xlsx)
            self.log_queue.put(("refresh_outputs", None))
            self.log_queue.put(("done", (True, f"{title} 执行完成")))
        except Exception as exc:
            self.log_queue.put(("log", f"\n[ERROR] {exc}\n"))
            self.log_queue.put(("done", (False, str(exc))))

    def _reader_thread(self, stream, out_queue):
        try:
            while True:
                line = stream.readline()
                if not line:
                    break
                out_queue.put(decode_output(line))
        finally:
            try:
                stream.close()
            except Exception:
                pass
            out_queue.put(None)

    def _terminate_process_tree(self, process):
        if process is None:
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    def stop_current_task(self):
        if not (self.worker and self.worker.is_alive()):
            return
        self.stop_event.set()
        with self.current_process_lock:
            process = self.current_process
        self._terminate_process_tree(process)
        self._append_log("\n[INFO] Stop requested. Waiting for the current task to exit...\n")
        self.status_var.set("正在停止当前任务...")

    def _run_process(self, step_name: str, command, cwd: Path):
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        pretty = subprocess.list2cmdline(command)
        self.log_queue.put(("log", f"\n>>> [{step_name}] {pretty}\n工作目录：{cwd}\n\n"))

        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            env=child_tool_env(),
        )

        with self.current_process_lock:
            self.current_process = process

        output_queue = queue.Queue()
        reader = threading.Thread(target=self._reader_thread, args=(process.stdout, output_queue), daemon=True)
        reader.start()

        started_at = time.monotonic()
        last_heartbeat_at = 0.0
        reader_finished = False

        while True:
            drained_any = False
            while True:
                try:
                    item = output_queue.get_nowait()
                except queue.Empty:
                    break
                drained_any = True
                if item is None:
                    reader_finished = True
                    continue
                self.log_queue.put(("log", item))

            if self.stop_event.is_set():
                self._terminate_process_tree(process)
                raise RuntimeError(f"{step_name} 已被用户停止。")

            now = time.monotonic()
            elapsed = int(now - started_at)
            if now - last_heartbeat_at >= HEARTBEAT_SECONDS:
                self.log_queue.put(("status", f"正在执行 {step_name} | 已运行 {elapsed}s"))
                last_heartbeat_at = now

            if reader_finished and process.poll() is not None and output_queue.empty():
                break

            if not drained_any:
                time.sleep(POLL_INTERVAL)

        return_code = process.wait()
        with self.current_process_lock:
            if self.current_process is process:
                self.current_process = None
        if return_code != 0:
            raise RuntimeError(f"{step_name} 返回了非 0 退出码：{return_code}")

    def _start_run(self, title: str, include_enscan: bool, include_pipeline: bool):
        try:
            snapshot = self._build_job_snapshot(include_enscan, include_pipeline)
        except Exception as exc:
            messagebox.showerror("启动失败", str(exc))
            return
        if include_enscan:
            self._clear_xlsx_output()
        self._start_worker(title, snapshot)

    def run_enscan(self):
        self._start_run("Enscan", include_enscan=True, include_pipeline=False)

    def run_pipeline(self):
        self._start_run("仅执行资产测绘", include_enscan=False, include_pipeline=True)
    def open_latest_result(self):
        latest_csv = Path(self.result_csv_var.get()) if self.result_csv_var.get().strip() else None
        if latest_csv and latest_csv.exists():
            self._open_path(latest_csv)
            return
        messagebox.showwarning("任务进行中", "请等待当前任务执行完成。")


if __name__ == "__main__":
    app = ZiWeiQiGui()
    app.mainloop()


# codex-write-test
