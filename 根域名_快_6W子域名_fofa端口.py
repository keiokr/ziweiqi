import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass


def _safe_write(text):
    try:
        sys.stdout.write(str(text))
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(str(text).encode(enc, errors="replace").decode(enc, errors="replace"))
    sys.stdout.flush()


scripts = [
    os.path.join(BASE_DIR, "core", "step01_cleanup_last_run.py"),
    os.path.join(BASE_DIR, "core", "step02_split_targets_domain_ip.py"),
    os.path.join(BASE_DIR, "core", "step03_prepare_fofa_url.py"),
    os.path.join(BASE_DIR, "core", "step04_run_fofamap.py"),
    os.path.join(BASE_DIR, "core", "step05_split_fofa_log.py"),
    os.path.join(BASE_DIR, "core", "step06_extract_fofa_ports_domains.py"),
    os.path.join(BASE_DIR, "core", "step07_extract_fofa_web_urls.py"),
    os.path.join(BASE_DIR, "core", "step08_enum_subdomains_6w.py"),
    os.path.join(BASE_DIR, "core", "step09_run_oneforall.py"),
    os.path.join(BASE_DIR, "core", "step10_run_subfinder.py"),
    os.path.join(BASE_DIR, "core", "step11_merge_subdomains.py"),
    os.path.join(BASE_DIR, "core", "step12_merge_fofa_domains.py"),
    os.path.join(BASE_DIR, "core", "step13_keyword_filter_domains.py"),
    os.path.join(BASE_DIR, "core", "step14_import_domains_to_sqlite.py"),
    os.path.join(BASE_DIR, "core", "step15_resolve_domains_to_ip.py"),
    os.path.join(BASE_DIR, "core", "step16_merge_filter_ip.py"),
    os.path.join(BASE_DIR, "core", "step17_run_masscan.py"),
    os.path.join(BASE_DIR, "core", "step18_filter_masscan_ip.py"),
    os.path.join(BASE_DIR, "core", "step19_merge_ports.py"),
    os.path.join(BASE_DIR, "core", "step20_run_fscan_port_fofa.py"),
    os.path.join(BASE_DIR, "core", "step21_extract_fscan_web.py"),
    os.path.join(BASE_DIR, "core", "step22_run_webfinder.py"),
    os.path.join(BASE_DIR, "core", "step23_extract_webfinder_csv.py"),
    os.path.join(BASE_DIR, "core", "step24_merge_all_web_sources.py"),
    os.path.join(BASE_DIR, "core", "step25_finalize_live_web.py"),
    os.path.join(BASE_DIR, "core", "step26_import_results_csv_to_sqlite.py"),
    os.path.join(BASE_DIR, "core", "step27_deduplicate_sqlite_results.py"),
    os.path.join(BASE_DIR, "core", "step28_export_final_results.py"),
]


def run_scripts(script_list):
    for script in script_list:
        print(f"Running {script}...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8:replace"
        env["PYTHONUTF8"] = "1"
        try:
            process = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env=env,
                errors="replace",
                cwd=BASE_DIR,
            )
            for line in process.stdout:
                try:
                    _safe_write(line)
                except UnicodeEncodeError:
                    pass
            process.wait()
            if process.returncode != 0:
                print(f"Script failed: {script} (exit={process.returncode})")
            else:
                print(f"Script finished: {script}")
        except Exception as exc:
            print(f"Script error: {script} -> {exc}")


if __name__ == "__main__":
    run_scripts(scripts)
