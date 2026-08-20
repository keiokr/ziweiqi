import hashlib
import json
import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_TMP_DIR = RESULTS_DIR / "tmp"
BACKUP_ROOT = PROJECT_ROOT / "backup"
ENSCAN_OUTS_DIR = PROJECT_ROOT / "tools" / "enscan" / "outs"
ONEFORALL_RESULTS_DIR = PROJECT_ROOT / "tools" / "OneForAll" / "results"
ENSCAN_RESULT_XLSX_PREFIX = "gongsi.txt批量查询任务结果"

ROOT_FILE_PATTERNS = [
    "allok.txt",
    "db.db",
    "error.txt",
    "error_.txt",
    "fscan+记录.txt",
    "ip.txt",
    "ip2.txt",
    "jieguo.txt",
    "masscan.txt",
    "mubiao.txt",
    "mubiao2.txt",
    "ports.txt",
    "result.txt",
    "results.csv",
    "results.xlsx",
    "results2.csv",
    "results2.db",
    "results2.sqlite",
    "url.txt",
    "yichang.txt",
    "*资产已去重_*.csv",
    "*资产已去重_*.txt",
    "ports_4000_*.txt",
    
]

RESULTS_FILE_PATTERNS = [
    "output.csv",
    "results.csv",
    "results2.csv",
    "results2.db",
    "results2.sqlite",
    "error_.txt",
    "*资产已去重_*.csv",
    "*资产已去重_*.txt",
]

TOOL_RUNTIME_FILES = [
    PROJECT_ROOT / "tools" / "domaintoIP" / "error.txt",
    PROJECT_ROOT / "tools" / "domaintoIP" / "result.txt",
    PROJECT_ROOT / "tools" / "domaintoIP" / "url.txt",
    PROJECT_ROOT / "tools" / "domaintoIP" / "yichang.txt",
    PROJECT_ROOT / "tools" / "enscan" / "enscan.gob",
    PROJECT_ROOT / "tools" / "FofaMap" / "fofamap.log",
    PROJECT_ROOT / "tools" / "FofaMap" / "url.txt",
    PROJECT_ROOT / "tools" / "fscan" / "ip.txt",
    PROJECT_ROOT / "tools" / "fscan" / "ports.txt",
    PROJECT_ROOT / "tools" / "subfinder" / "domains.txt",
    PROJECT_ROOT / "tools" / "subfinder" / "subfinderok.txt",
    PROJECT_ROOT / "tools" / "ksubdomain" / "domains.txt",
    PROJECT_ROOT / "tools" / "ksubdomain" / "ksubok.txt",
    PROJECT_ROOT / "tools" / "masscan" / "ip2.txt",
    PROJECT_ROOT / "tools" / "masscan" / "ip.txt",
    PROJECT_ROOT / "tools" / "masscan" / "masscan.txt",
    PROJECT_ROOT / "tools" / "OneForAll" / "domains.txt",
    PROJECT_ROOT / "tools" / "OneForAll" / "OneForAllok.txt",
    PROJECT_ROOT / "tools" / "tiquguanjianzi" / "guanjianzi.txt",
    PROJECT_ROOT / "tools" / "tiquguanjianzi" / "guanjianzi2.txt",
    PROJECT_ROOT / "tools" / "tiquguanjianzi" / "mubiao.txt",
    PROJECT_ROOT / "tools" / "tiquguanjianzi" / "mubiao2.txt",
    PROJECT_ROOT / "tools" / "weblive" / "url.txt",
    PROJECT_ROOT / "tools" / "weblive2" / "url.txt",
]


def iter_matches(base: Path, patterns):
    if not base.exists():
        return
    for pattern in patterns:
        yield from base.glob(pattern)


def should_skip_file(path: Path) -> bool:
    resolved = path.resolve()
    if BACKUP_ROOT in resolved.parents:
        return True
    if resolved == (PROJECT_ROOT / "scanIPAndDomain.txt").resolve():
        return True
    if (
        resolved.suffix.lower() == ".xlsx"
        and ENSCAN_OUTS_DIR.resolve() in resolved.parents
        and resolved.name.startswith(ENSCAN_RESULT_XLSX_PREFIX)
    ):
        return True
    return False


def collect_runtime_files():
    files = set()

    for path in iter_matches(PROJECT_ROOT, ROOT_FILE_PATTERNS):
        if path.is_file() and not should_skip_file(path):
            files.add(path.resolve())

    for path in iter_matches(RESULTS_DIR, RESULTS_FILE_PATTERNS):
        if path.is_file() and not should_skip_file(path):
            files.add(path.resolve())

    for base in (RESULTS_TMP_DIR, ENSCAN_OUTS_DIR, ONEFORALL_RESULTS_DIR):
        if base.exists():
            for path in base.rglob("*"):
                if path.is_file() and not should_skip_file(path):
                    files.add(path.resolve())

    for path in TOOL_RUNTIME_FILES:
        if path.is_file() and not should_skip_file(path):
            files.add(path.resolve())

    return sorted(files)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup_dir() -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def allocate_backup_path(backup_dir: Path, source: Path) -> Path:
    relative = source.relative_to(PROJECT_ROOT)
    target = backup_dir / "files" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    index = 1
    while True:
        candidate = target.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def backup_files(backup_dir: Path, files):
    manifest = []
    for path in files:
        target = allocate_backup_path(backup_dir, path)
        shutil.copy2(path, target)
        manifest.append(
            {
                "source": str(path.relative_to(PROJECT_ROOT)),
                "backup": str(target.relative_to(backup_dir)),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
        print(f"已备份: {path} -> {target}")

    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_files(files):
    for path in files:
        if not path.exists():
            continue
        path.unlink()
        print(f"已删除文件: {path}")


def ensure_runtime_dirs():
    for path in (RESULTS_TMP_DIR, ENSCAN_OUTS_DIR, ONEFORALL_RESULTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def execute_operations():
    files = collect_runtime_files()
    if files:
        backup_dir = create_backup_dir()
        backup_files(backup_dir, files)
        delete_files(files)
        print(f"备份目录: {backup_dir}")
    else:
        print("没有发现上次运行遗留的产物，无需备份和删除。")

    ensure_runtime_dirs()
    print("清理完成，可以开始本次运行。")


if __name__ == "__main__":
    execute_operations()
