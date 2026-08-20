import os
import glob
import subprocess
import sys
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
ONEFORALL_DIR = os.path.join(PROJECT_ROOT, "tools", "OneForAll")

# 目录与文件路径配置
oneforall_script = os.path.join(ONEFORALL_DIR, "oneforall.py")
domains_file = os.path.join(ONEFORALL_DIR, "domains.txt")
results_dir = os.path.join(ONEFORALL_DIR, "results")
output_file = os.path.join(ONEFORALL_DIR, "OneForAllok.txt")

file_patterns_to_delete = ["*.txt", "*.json", "*.csv", "*.log", "*.sqlite3"]


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def delete_files():
    for pattern in file_patterns_to_delete:
        files_to_delete = glob.glob(os.path.join(results_dir, "**", pattern), recursive=True)
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                print(f"已删除文件: {file_path}")
            except Exception as e:
                print(f"删除文件时出错: {file_path}, 错误: {e}")

    print(f"已清理 {results_dir} 目录下的运行文件。")


def split_file(input_file, lines_per_file=20):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    num_files = (total_lines // lines_per_file) + (1 if total_lines % lines_per_file else 0)

    split_files = []
    for i in range(num_files):
        split_file_path = f"{input_file.rsplit('.', 1)[0]}_{i + 1}.txt"
        with open(split_file_path, "w", encoding="utf-8") as f:
            f.writelines(lines[i * lines_per_file: (i + 1) * lines_per_file])
        split_files.append(split_file_path)
        print(f"文件 {split_file_path} 已创建，每份最多 {lines_per_file} 行")

    return split_files


def run_oneforall(input_file):
    command = [
        sys.executable,
        oneforall_script,
        "--targets",
        input_file,
        "--brute",
        "True",
        "--req",
        "False",
        "run",
    ]
    try:
        print(f"正在执行 OneForAll，输入文件: {input_file}")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=ONEFORALL_DIR,
            env=child_env(),
        )
        for line in process.stdout:
            print(line, end="", flush=True)

        process.wait()
        if process.returncode == 0:
            print("\nOneForAll 脚本执行完成。")
        else:
            print(f"\nOneForAll 脚本执行失败，退出码: {process.returncode}")
            raise SystemExit(1)
    except Exception as e:
        print(f"调用 OneForAll 时出错: {e}")
        raise SystemExit(1)


def is_valid_domain(s: str) -> bool:
    """简单域名校验，过滤明显不是域名的行"""
    if not s or len(s) > 253:
        return False
    parts = s.split('.')
    if len(parts) < 2:
        return False
    # 仅允许字母、数字、连字符、点，且不能以连字符或点开头/结尾
    return bool(re.match(r'^(?![.-])[a-zA-Z0-9.-]{1,252}(?<![.-])$', s))


def copy_matching_files():
    """安全合并 OneForAll 结果，避免换行粘连并自动去重"""
    matching_files = glob.glob(os.path.join(results_dir, "**", "*.txt"), recursive=True)
    matching_files = [f for f in matching_files if os.path.isfile(f)]

    if not matching_files:
        print("未找到任何 .txt 结果文件，请检查 OneForAll 是否正常输出。")
        return

    seen = set()
    total_domains = 0
    stuck_lines_fixed = 0

    try:
        with open(output_file, "w", encoding="utf-8") as outfile:
            for file_path in matching_files:
                print(f"正在合并文件: {file_path}")
                with open(file_path, "r", encoding="utf-8", errors="replace") as infile:
                    for line in infile:
                        domain = line.strip()
                        if not domain:
                            continue

                        # 一行过长且含多个点，极可能是粘连行，尝试拆分
                        if len(domain) > 100 and domain.count('.') > 3:
                            candidates = re.findall(
                                r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
                                domain
                            )
                            for d in candidates:
                                if d not in seen and is_valid_domain(d):
                                    outfile.write(d + '\n')
                                    seen.add(d)
                                    total_domains += 1
                            if candidates:
                                stuck_lines_fixed += 1
                        else:
                            if domain not in seen and is_valid_domain(domain):
                                outfile.write(domain + '\n')
                                seen.add(domain)
                                total_domains += 1

        print(f"所有结果已去重合并到 {output_file}")
        print(f"写入有效域名总数: {total_domains}")
        if stuck_lines_fixed:
            print(f"其中自动修复粘连行数: {stuck_lines_fixed} 处")

    except Exception as e:
        print(f"合并结果文件时出错: {e}")
        raise SystemExit(1)


def delete_split_files(split_files):
    for split_file in split_files:
        try:
            os.remove(split_file)
            print(f"已删除文件: {split_file}")
        except Exception as e:
            print(f"删除文件时出错: {split_file}, 错误: {e}")


if __name__ == "__main__":
    split_files = split_file(domains_file)
    for split_file in split_files:
        run_oneforall(split_file)
    copy_matching_files()
    delete_files()
    delete_split_files(split_files)
