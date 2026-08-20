import os
import subprocess
import time
import sys
import io
from colorama import init, deinit, Fore
from console_utils import configure_stdio

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
FOFA_DIR = os.path.join(PROJECT_ROOT, "tools", "FofaMap")

configure_stdio()


def delete_log_file():
    """删除 FofaMap/fofamap.log 文件，如果文件存在"""
    log_file = os.path.join(FOFA_DIR, "fofamap.log")
    
    if os.path.exists(log_file):
        try:
            os.remove(log_file)
            print(f"已删除 {log_file}")
        except Exception as e:
            print(f"删除 {log_file} 时出错: {e}")
    else:
        print(f"{log_file} 文件已删除！")

    # 创建一个空白的 log 文件
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            pass
        print(f"已创建空白文件 {log_file}")
    except Exception as e:
        print(f"创建 {log_file} 时出错: {e}")

def run_fofamap():
    """运行 FofaMap/fofamap.py 程序"""
    fofa_path = os.path.join(FOFA_DIR, "fofamap.py")
    url_file = os.path.join(FOFA_DIR, "url.txt")

    print("当前工作目录:", os.getcwd())
    
    python_path = sys.executable
    try:
        subprocess.run([python_path, "--version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("未找到 Python，请确保它已安装并配置在环境变量中！")
        return
    
    if os.path.exists(fofa_path):
        try:
            # 禁用 colorama 的颜色输出
            init(strip=True)  # 禁用颜色输出

            process = subprocess.Popen(
                [python_path, fofa_path, "-bq", url_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=FOFA_DIR,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8:replace", "PYTHONUNBUFFERED": "1"},
            )

            # 合并读取 stdout/stderr，避免子进程输出过多时互相阻塞。
            for line in process.stdout:
                try:
                    print(line.strip())
                except UnicodeEncodeError:
                    pass

            process.wait()
            if process.returncode == 0:
                print("FofaMap/fofamap.py 执行成功！")
            else:
                print(f"FofaMap 执行失败，返回码: {process.returncode}")
        except Exception as e:
            print(f"运行 FofaMap/fofamap.py 时出错: {e}")
        finally:
            deinit()  # 关闭 colorama，恢复原始设置
    else:
        print(f"文件 {fofa_path} 不存在！")

if __name__ == "__main__":
    delete_log_file()
    run_fofamap()
