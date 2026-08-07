from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from urllib.parse import urlparse
from app_icon import apply_app_icon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOMAINTOIP_DIR = PROJECT_ROOT / "tools" / "domaintoIP"
RESULTS_DIR = PROJECT_ROOT / "results"


IPV4_RE = re.compile(
    r"(?<!\d)(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?!\d)"
)
URL_RE = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+")
DOMAIN_RE = re.compile(
    r"(?<![a-zA-Z0-9_-])(?:\*\.)?"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63}(?![a-zA-Z0-9_-])"
)

MULTI_LEVEL_SUFFIXES = {
    "ac.cn", "com.cn", "edu.cn", "gov.cn", "mil.cn", "net.cn", "org.cn",
    "ah.cn", "bj.cn", "cq.cn", "fj.cn", "gd.cn", "gs.cn", "gx.cn", "gz.cn",
    "ha.cn", "hb.cn", "he.cn", "hi.cn", "hk.cn", "hl.cn", "hn.cn", "jl.cn",
    "js.cn", "jx.cn", "ln.cn", "mo.cn", "nm.cn", "nx.cn", "qh.cn", "sc.cn",
    "sd.cn", "sh.cn", "sn.cn", "sx.cn", "tj.cn", "tw.cn", "xj.cn", "xz.cn",
    "yn.cn", "zj.cn", "co.uk", "ac.uk", "gov.uk", "ltd.uk", "me.uk", "net.uk",
    "org.uk", "plc.uk", "sch.uk", "com.au", "edu.au", "gov.au", "id.au", "net.au",
    "org.au", "asn.au", "com.hk", "edu.hk", "gov.hk", "idv.hk", "net.hk", "org.hk",
    "com.tw", "edu.tw", "gov.tw", "idv.tw", "net.tw", "org.tw", "co.jp", "ac.jp",
    "ad.jp", "ed.jp", "go.jp", "gr.jp", "lg.jp", "ne.jp", "or.jp", "com.sg",
    "edu.sg", "gov.sg", "net.sg", "org.sg", "per.sg", "com.my", "edu.my", "gov.my",
    "net.my", "org.my", "co.kr", "ne.kr", "or.kr", "re.kr", "pe.kr", "go.kr",
    "mil.kr", "ac.kr", "co.nz", "ac.nz", "geek.nz", "gen.nz", "govt.nz", "health.nz",
    "iwi.nz", "kiwi.nz", "maori.nz", "mil.nz", "net.nz", "org.nz", "school.nz",
}
COMMON_COUNTRY_SECOND_LEVELS = {
    "ac", "co", "com", "edu", "gov", "mil", "net", "nom", "org", "sch",
}
READ_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1")

MODE_CONFIGS = {
    "keep": {
        "title": "保留模式",
        "desc": "保留命中的 URL，输出 url_ok.txt。",
        "primary_file": "url_ok.txt",
        "primary_label": "保留URL",
        "primary_attr": "kept_url_lines",
    },
    "reverse": {
        "title": "反向模式",
        "desc": "去除命中的 URL，输出 url_reverse_ok.txt。",
        "primary_file": "url_reverse_ok.txt",
        "primary_label": "反向保留URL",
        "primary_attr": "removed_url_lines",
    },
}


@dataclass(frozen=True)
class InputTarget:
    mode: str
    value: str


@dataclass
class BatchFilterContext:
    input_targets: list[InputTarget]
    matched_result_lines: list[str]
    matched_root_domains: set[str]
    matched_domains: set[str]
    matched_ips: set[str]
    domain_related_ips: set[str]
    kept_url_lines: list[str]
    removed_url_lines: list[str]

    @property
    def original_url_count(self) -> int:
        return len(self.kept_url_lines) + len(self.removed_url_lines)



def read_text_auto(path: Path) -> str:
    data = path.read_bytes()
    for encoding in READ_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")



def write_lines(path: Path, lines: list[str]) -> None:
    text = "\n".join(lines)
    if lines:
        text += "\n"
    path.write_text(text, encoding="utf-8")



def is_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        return False



def normalize_host_or_ip(value: str) -> str:
    text = value.strip().strip('"\'').strip()
    if not text:
        return ""

    if "://" in text:
        parsed = urlparse(text)
        if parsed.hostname:
            return parsed.hostname.lower().rstrip(".")

    if text.startswith("//"):
        parsed = urlparse(f"http:{text}")
        if parsed.hostname:
            return parsed.hostname.lower().rstrip(".")

    text = text.split("/", 1)[0]
    text = text.rsplit("@", 1)[-1]
    text = text.strip("[](){}<>.,;\"' ").rstrip(".").lower()
    if not text:
        return ""

    if text.count(":") == 1:
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host

    return text



def get_registrable_domain(host: str) -> str:
    host = normalize_host_or_ip(host)
    if not host or is_ipv4(host):
        return host

    labels = [part for part in host.split(".") if part]
    if len(labels) <= 2:
        return ".".join(labels)

    last_two = ".".join(labels[-2:])
    if last_two in MULTI_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])

    if len(labels[-1]) == 2 and labels[-2] in COMMON_COUNTRY_SECOND_LEVELS:
        return ".".join(labels[-3:])

    return ".".join(labels[-2:])



def normalize_root_domain_or_ip(value: str) -> InputTarget:
    normalized = normalize_host_or_ip(value)
    if not normalized:
        raise ValueError("输入为空，请删掉空行后重试。")

    if is_ipv4(normalized):
        return InputTarget(mode="ip", value=normalized)

    if "." not in normalized:
        raise ValueError(f"不是有效根域名或 IP: {value}")

    root_domain = get_registrable_domain(normalized)
    if normalized != root_domain:
        raise ValueError(f"检测到子域名，不允许输入子域名: {value}")

    return InputTarget(mode="domain", value=root_domain)



def parse_targets(text: str) -> list[InputTarget]:
    raw_lines = [line.strip() for line in text.replace(",", "\n").splitlines()]
    candidates = [line for line in raw_lines if line]
    if not candidates:
        raise ValueError("请输入备案资产，支持根域名和ip。")

    parsed: list[InputTarget] = []
    seen: set[tuple[str, str]] = set()
    errors: list[str] = []

    for line in candidates:
        try:
            item = normalize_root_domain_or_ip(line)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        key = (item.mode, item.value)
        if key not in seen:
            seen.add(key)
            parsed.append(item)

    if errors:
        raise ValueError("输入校验失败:\n" + "\n".join(errors[:20]))

    return parsed



def extract_ipv4s(text: str) -> set[str]:
    return set(IPV4_RE.findall(text))



def extract_domains(text: str) -> set[str]:
    domains: set[str] = set()

    for url in URL_RE.findall(text):
        host = normalize_host_or_ip(url)
        if host and not is_ipv4(host):
            domains.add(host)

    for match in DOMAIN_RE.findall(text):
        host = normalize_host_or_ip(match.lstrip("*."))
        if host and not is_ipv4(host):
            domains.add(host)

    return domains



def analyze_files(targets_text: str, result_path: Path, url_path: Path) -> BatchFilterContext:
    targets = parse_targets(targets_text)
    result_lines = [line.strip() for line in read_text_auto(result_path).splitlines() if line.strip()]
    url_lines = [line.strip() for line in read_text_auto(url_path).splitlines() if line.strip()]

    matched_result_lines: list[str] = []
    matched_root_domains: set[str] = set()
    matched_domains: set[str] = set()
    matched_ips: set[str] = set()
    domain_related_ips: set[str] = set()

    domain_targets = {item.value for item in targets if item.mode == "domain"}
    ip_targets = {item.value for item in targets if item.mode == "ip"}

    for line in result_lines:
        ips = extract_ipv4s(line)
        domains = extract_domains(line)
        roots = {get_registrable_domain(domain) for domain in domains if domain}

        matched_by_ip = bool(ip_targets.intersection(ips))
        matched_by_domain = bool(domain_targets.intersection(roots))
        if not (matched_by_ip or matched_by_domain):
            continue

        matched_result_lines.append(line)
        matched_ips.update(ips)
        matched_domains.update(domains)
        matched_root_domains.update(roots)
        if matched_by_domain:
            domain_related_ips.update(ips)

    kept_url_lines: list[str] = []
    removed_url_lines: list[str] = []

    for line in url_lines:
        if should_keep_url_line(line, domain_targets, ip_targets, domain_related_ips):
            kept_url_lines.append(line)
        else:
            removed_url_lines.append(line)

    return BatchFilterContext(
        input_targets=targets,
        matched_result_lines=matched_result_lines,
        matched_root_domains=matched_root_domains,
        matched_domains=matched_domains,
        matched_ips=matched_ips,
        domain_related_ips=domain_related_ips,
        kept_url_lines=kept_url_lines,
        removed_url_lines=removed_url_lines,
    )



def should_keep_url_line(
    line: str,
    domain_targets: set[str],
    ip_targets: set[str],
    domain_related_ips: set[str],
) -> bool:
    host = normalize_host_or_ip(line)
    if not host:
        return False

    if is_ipv4(host):
        return host in ip_targets or host in domain_related_ips

    root = get_registrable_domain(host)
    return root in domain_targets



def save_mode_output(context: BatchFilterContext, output_dir: Path, mode_key: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    config = MODE_CONFIGS[mode_key]
    output_path = output_dir / config["primary_file"]
    output_lines = list(getattr(context, config["primary_attr"]))
    write_lines(output_path, output_lines)
    return output_path


def latest_file(base: Path, pattern: str) -> Path | None:
    files = [item for item in base.glob(pattern) if item.is_file()]
    if not files:
        return None
    return max(files, key=lambda item: item.stat().st_mtime)


def latest_file_by_patterns(base: Path, patterns: list[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(item for item in base.glob(pattern) if item.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


class DomainIpFilterGui:
    def __init__(self, root: Tk) -> None:
        self.root = root
        apply_app_icon(self.root, app_id="ziweiqi.desktop.domain-filter")
        self.root.title("By：ziweiqi")
        self.root.geometry("1120x760")
        self.root.minsize(1040, 700)

        self.workdir = PROJECT_ROOT
        self.last_output_path: Path | None = None

        self.result_file_var = StringVar(value=str(self._default_result_file()))
        self.url_file_var = StringVar(value=str(self._default_url_file()))
        self.output_dir_var = StringVar(value=str(PROJECT_ROOT))
        self.mode_var = StringVar(value="keep")
        self.summary_var = StringVar(value="等待开始。")
        self._apply_env_defaults()

        self._build_ui()
        self._center_window()

    def _apply_env_defaults(self) -> None:
        result_file = os.environ.get("ZIWEIQI_RESULT_FILE", "").strip()
        url_file = os.environ.get("ZIWEIQI_URL_FILE", "").strip()
        output_dir = os.environ.get("ZIWEIQI_OUTPUT_DIR", "").strip()
        if result_file:
            self.result_file_var.set(result_file)
        if url_file:
            self.url_file_var.set(url_file)
        if output_dir:
            self.output_dir_var.set(output_dir)

    def _default_result_file(self) -> Path:
        candidates = [
            DOMAINTOIP_DIR / "result.txt",
            PROJECT_ROOT / "result.txt",
            PROJECT_ROOT / "results.txt",
        ]
        for path in candidates:
            if path.exists():
                return path
        return DOMAINTOIP_DIR / "result.txt"

    def _default_url_file(self) -> Path:
        latest_asset_txt = latest_file_by_patterns(
            RESULTS_DIR,
            ["*资产已去重_*.txt", "*_results2.txt"],
        )
        if latest_asset_txt:
            return latest_asset_txt
        candidates = [
            PROJECT_ROOT / "url.txt",
            RESULTS_DIR / "url.txt",
        ]
        for path in candidates:
            if path.exists():
                return path
        return RESULTS_DIR / "url.txt"

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=BOTH, expand=True)

        title = ttk.Label(main, text="目标单位出局资产提取及剔除工具", font=("Microsoft YaHei UI", 14, "bold"))
        title.pack(anchor="w")

        desc = ttk.Label(
            main,
            text=(
                "只需要输入备案根域名及备案ip资产即可，只支持根域名或 IPv4，一行一个，"
                "从result.txt 中提取到匹配根域的子域名行的对应ip，再处理url.txt中匹配包含的根域名和ip地址进行提取或剔除保存。"
            ),
            wraplength=1180,
            justify="left",
        )
        desc.pack(anchor="w", pady=(6, 12))

        target_frame = ttk.LabelFrame(main, text="批量输入目标", padding=10)
        target_frame.pack(fill=BOTH, pady=(0, 8))

        tip = ttk.Label(
            target_frame,
            text="只允许输入根域名或 IP。示例：baidu.com.cn 或 110.242.68.4。",
            wraplength=1140,
            justify="left",
        )
        tip.pack(anchor="w")

        target_btns = ttk.Frame(target_frame)
        target_btns.pack(fill=X, pady=(8, 6))
        ttk.Button(target_btns, text="导入目标文件", command=self._import_targets).pack(side=LEFT)
        ttk.Button(target_btns, text="清空输入", command=self._clear_targets).pack(side=LEFT, padx=8)
        ttk.Button(target_btns, text="示例填充", command=self._fill_example).pack(side=LEFT)

        self.target_text = ScrolledText(target_frame, height=10)
        self.target_text.pack(fill=BOTH, expand=True)

        self._build_path_selector(main, "域名及对应ip文件、domaintoip_results.txt", self.result_file_var, self._choose_result_file)
        self._build_path_selector(main, "要去重的url文件", self.url_file_var, self._choose_url_file)
        self._build_path_selector(main, "输出目录", self.output_dir_var, self._choose_output_dir, choose_dir=True)

        mode_frame = ttk.LabelFrame(main, text="模式", padding=8)
        mode_frame.pack(fill=X, pady=(0, 8))
        ttk.Radiobutton(mode_frame, text=MODE_CONFIGS["keep"]["title"], value="keep", variable=self.mode_var).pack(side=LEFT)
        ttk.Radiobutton(mode_frame, text=MODE_CONFIGS["reverse"]["title"], value="reverse", variable=self.mode_var).pack(side=LEFT, padx=12)
        ttk.Label(mode_frame, textvariable=self.summary_var).pack(side=RIGHT)

        action_frame = ttk.Frame(main)
        action_frame.pack(fill=X, pady=(0, 10))
        ttk.Button(action_frame, text="开始分析并导出", command=self.on_analyze).pack(side=LEFT)
        ttk.Button(action_frame, text="打开输出目录", command=self._open_output_dir).pack(side=LEFT, padx=8)
        ttk.Button(action_frame, text="清空日志", command=self.clear_log).pack(side=LEFT, padx=8)
        ttk.Label(action_frame, textvariable=self.summary_var).pack(side=RIGHT)

        log_frame = ttk.LabelFrame(main, text="运行日志 / 结果预览", padding=8)
        log_frame.pack(fill=BOTH, expand=True)
        self.log_text = ScrolledText(log_frame, height=28)
        self.log_text.pack(fill=BOTH, expand=True)
        self.log_text.configure(state="disabled")

    def _center_window(self) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(20, (screen_height - height) // 6)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_path_selector(
        self,
        parent: ttk.Frame,
        title: str,
        variable: StringVar,
        command,
        choose_dir: bool = False,
    ) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill=X, pady=(0, 8))
        ttk.Entry(frame, textvariable=variable).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        ttk.Button(frame, text="选择目录" if choose_dir else "选择文件", command=command).pack(side=LEFT)

    def log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", END)
        self.log_text.configure(state="disabled")
        self.summary_var.set("日志已清空。")

    def _import_targets(self) -> None:
        path = filedialog.askopenfilename(
            title="选择目标列表文件",
            initialdir=self._safe_initial_dir("."),
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return

        content = read_text_auto(Path(path))
        self.target_text.delete("1.0", END)
        self.target_text.insert("1.0", content)
        line_count = len([line for line in content.splitlines() if line.strip()])
        self.summary_var.set(f"已导入 {line_count} 条目标。")

    def _clear_targets(self) -> None:
        self.target_text.delete("1.0", END)
        self.summary_var.set("输入已清空。")

    def _fill_example(self) -> None:
        self.target_text.delete("1.0", END)
        self.target_text.insert("1.0", "baidu.com.cn\n110.242.68.4\n")
        self.summary_var.set("已填充示例。")

    def _choose_result_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 result.txt",
            initialdir=self._safe_initial_dir(self.result_file_var.get()),
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if path:
            self.result_file_var.set(path)

    def _choose_url_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 url.txt",
            initialdir=self._safe_initial_dir(self.url_file_var.get()),
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if path:
            self.url_file_var.set(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=self._safe_initial_dir(self.output_dir_var.get()),
        )
        if path:
            self.output_dir_var.set(path)

    def _open_output_dir(self) -> None:
        output_dir = Path(self.output_dir_var.get()).expanduser()
        if not output_dir.exists():
            messagebox.showerror("打开失败", f"输出目录不存在: {output_dir}")
            return
        try:
            os.startfile(output_dir)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc))

    def _safe_initial_dir(self, raw_path: str) -> str:
        path = Path(raw_path).expanduser()
        if path.exists():
            return str(path if path.is_dir() else path.parent)
        return str(self.workdir)

    def _collect_target_text(self) -> str:
        return self.target_text.get("1.0", END).strip()

    def on_analyze(self) -> None:
        try:
            result_path, url_path, output_dir, targets_text = self._collect_inputs()
            context = analyze_files(targets_text, result_path, url_path)
            mode_key = self._current_mode()
            output_path = save_mode_output(context, output_dir, mode_key)
        except Exception as exc:
            messagebox.showerror("分析失败", str(exc))
            self.summary_var.set("分析失败。")
            return

        self.last_output_path = output_path
        config = MODE_CONFIGS[self._current_mode()]
        self.log("")
        self.log("=" * 88)
        self.log(f"当前模式: {config['title']}")
        self.log(f"输入目标数量: {len(context.input_targets)}")
        self.log(f"result 命中行数: {len(context.matched_result_lines)}")
        self.log(f"命中根域名数量: {len(context.matched_root_domains)}")
        self.log(f"命中子域名数量: {len(context.matched_domains)}")
        self.log(f"命中 IP 数量: {len(context.matched_ips)}")
        self.log(f"{config['primary_label']} 行数: {len(getattr(context, config['primary_attr']))}")
        self.log(f"输出目录: {output_dir}")
        self.log(f"已生成: {output_path}")

        self.summary_var.set(f"完成: {config['primary_file']} = {len(getattr(context, config['primary_attr']))}")
        messagebox.showinfo("完成", f"结果已生成:\n{output_path}")

    def _collect_inputs(self) -> tuple[Path, Path, Path, str]:
        result_path = Path(self.result_file_var.get()).expanduser()
        url_path = Path(self.url_file_var.get()).expanduser()
        output_dir = Path(self.output_dir_var.get()).expanduser()
        targets_text = self._collect_target_text()

        if not targets_text:
            raise ValueError("请输入备案资产根域名或ip。")
        if not result_path.is_file():
            raise FileNotFoundError(f"result.txt 不存在: {result_path}")
        if not url_path.is_file():
            raise FileNotFoundError(f"url.txt 不存在: {url_path}")
        if output_dir.exists() and not output_dir.is_dir():
            raise NotADirectoryError(f"输出目录不是文件夹: {output_dir}")

        return result_path, url_path, output_dir, targets_text

    def _current_mode(self) -> str:
        mode = self.mode_var.get().strip()
        return mode if mode in MODE_CONFIGS else "keep"


def main() -> None:
    root = Tk()
    DomainIpFilterGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
