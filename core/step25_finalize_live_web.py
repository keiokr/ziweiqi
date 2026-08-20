import os
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env

def run_quanhangpipei2():
    """
    运行 tiquguanjianzi/quanhangpipei2.py。
    """
    try:
        script_path = os.path.join(PROJECT_ROOT, "tools", "tiquguanjianzi", "quanhangpipei2.py")
        subprocess.run([sys.executable, script_path], check=True, cwd=PROJECT_ROOT, env=child_env())
        print("成功运行 tiquguanjianzi/quanhangpipei2.py")
    except subprocess.CalledProcessError as e:
        print(f"运行 tiquguanjianzi/quanhangpipei2.py 时发生错误: {e}")

def copy_jieguo2_to_weblive():
    """
    复制 jieguo2.txt 到 weblive/url.txt。
    """
    source_file = os.path.join(PROJECT_ROOT, "results", "tmp", "32_jieguo2.txt")
    destination_file = os.path.join(PROJECT_ROOT, "tools", "weblive", "url.txt")
    
    try:
        shutil.copy(source_file, destination_file)
        print(f"文件 {source_file} 已成功复制到 {destination_file}")
    except FileNotFoundError:
        print(f"源文件 {source_file} 不存在，无法复制。")
    except Exception as e:
        print(f"复制文件时发生错误: {e}")

def run_whichalive():
    """
    运行 weblive/whichalive.py。
    """
    try:
        script_path = os.path.join(PROJECT_ROOT, "tools", "weblive", "whichalive.py")
        url_file = os.path.join(PROJECT_ROOT, "tools", "weblive", "url.txt")
        command = [sys.executable, script_path, "-f", url_file, "-t", "20", "--try-again"]
        subprocess.run(command, check=True, cwd=PROJECT_ROOT, env=child_env())
        print(f"成功运行 {script_path}")
    except subprocess.CalledProcessError as e:
        print(f"运行 {script_path} 时发生错误: {e}")
    except FileNotFoundError:
        print(f"文件 {script_path} 或 {url_file} 不存在，无法运行。")

def main():
    # 第一步：运行 tiquguanjianzi/quanhangpipei2.py
    run_quanhangpipei2()

    # 第二步：复制 jieguo2.txt 到 weblive/url.txt
    copy_jieguo2_to_weblive()

    # 第三步：运行 weblive/whichalive.py
    run_whichalive()

if __name__ == "__main__":
    main()
