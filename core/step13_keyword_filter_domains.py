import os
import shutil
import re
import time
import subprocess
import sys
from encoding_utils import read_lines_guess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def merge_and_process_files():
    """处理 1_enscangenyuming.txt 文件，去除无效行，保存到 21_guanjian_1.txt"""
    file1_path = r".\results\tmp\1_enscangenyuming.txt"  # 只处理这个文件
    output_file = r".\results\tmp\21_guanjian_1.txt"

    if os.path.exists(file1_path):
        try:
            # 读取文件内容
            lines1 = read_lines_guess(file1_path)

            # 去除首尾空格，空白行，重复行，IP 地址，中文字符
            processed_lines = set()  # 使用集合去重
            for line in lines1:
                line = line.strip()
                if line and not is_ip(line) and not contains_chinese(line):  # 过滤掉空白行、IP和中文
                    processed_lines.add(line)

            # 保存处理后的内容到文件
            with open(output_file, "w", encoding="utf-8") as f:
                for line in sorted(processed_lines):
                    f.write(line + "\n")

            print(f"处理后的内容已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件时出错: {e}")
    else:
        print(f"文件 {file1_path} 不存在！")

def is_ip(line):
    """检查行是否为IP地址"""
    ip_pattern = r"(\d{1,3}\.){3}\d{1,3}"
    return re.match(ip_pattern, line) is not None

def contains_chinese(line):
    """检查行是否包含中文字符"""
    return any('\u4e00' <= char <= '\u9fff' for char in line)

def copy_files():
    """复制文件到目标路径"""
    try:
        shutil.copy(
            os.path.join(PROJECT_ROOT, "results", "tmp", "21_guanjian_1.txt"),
            os.path.join(PROJECT_ROOT, "tools", "tiquguanjianzi", "guanjianzi.txt"),
        )
        shutil.copy(
            os.path.join(PROJECT_ROOT, "results", "tmp", "20_ziyuming_all.txt"),
            os.path.join(PROJECT_ROOT, "tools", "tiquguanjianzi", "mubiao.txt"),
        )
        print("文件复制完成")
    except Exception as e:
        print(f"复制文件时出错: {e}")

def run_python_script():
    """运行 youcepipei2.py 脚本"""
    script_path = os.path.join(PROJECT_ROOT, "tools", "tiquguanjianzi", "youcepipei2.py")
    if os.path.exists(script_path):
        try:
            subprocess.run(
                [sys.executable, script_path],
                cwd=PROJECT_ROOT,
                env=child_env(),
                check=False,
            )
            print(f"脚本 {script_path} 执行完成")
        except Exception as e:
            print(f"执行脚本时出错: {e}")
    else:
        print(f"脚本 {script_path} 不存在！")

if __name__ == "__main__":
    try:
        # 合并并处理文件
        merge_and_process_files()
    except Exception as e:
        print(f"合并处理文件时出错: {e}")

    try:
        # 复制文件到目标路径
        copy_files()
    except Exception as e:
        print(f"复制文件时出错: {e}")

    try:
        # 运行 Python 脚本
        run_python_script()
    except Exception as e:
        print(f"运行脚本时出错: {e}")

