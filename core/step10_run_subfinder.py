import os
import subprocess

from console_utils import configure_stdio
from encoding_utils import read_lines_guess


configure_stdio()


def child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def split_file(input_file, lines_per_file=10):
    """将输入文件按固定行数分割成多个文件。"""
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在！")
        return []

    lines = read_lines_guess(input_file)
    total_files = (len(lines) + lines_per_file - 1) // lines_per_file
    output_files = []

    for i in range(total_files):
        start = i * lines_per_file
        end = min((i + 1) * lines_per_file, len(lines))
        output_file = f"{input_file.rsplit('.', 1)[0]}_{i + 1}.txt"
        with open(output_file, "w", encoding="utf-8", errors="replace", newline="\n") as f_out:
            f_out.write("\n".join(lines[start:end]) + "\n")
        output_files.append(output_file)
        print(f"分割文件 {output_file} 已生成")

    return output_files


def process_single_file(split_file_name, subfinder_exe, output_file):
    """对单个分割文件执行 subfinder。"""
    command = [subfinder_exe, "-nc", "-timeout", "10", "-dL", split_file_name, "-o", output_file]
    print(f"正在执行命令: {' '.join(command)}")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=child_env(),
        )
        for line in process.stdout:
            print(line, end="", flush=True)

        process.wait()
        if process.returncode == 0:
            print(f"subfinder 执行完成，结果已保存到 {output_file}")
            return True

        print(f"subfinder 执行失败，返回码: {process.returncode}")
        return False
    except FileNotFoundError:
        print(f"找不到 {subfinder_exe}，请检查路径是否正确。")
        return False


def merge_unique_files(input_files, output_file):
    """合并多个结果文件，按出现顺序去重。"""
    seen = set()
    merged = []
    for file_path in input_files:
        if not os.path.exists(file_path):
            continue
        for line in read_lines_guess(file_path):
            value = line.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)

    with open(output_file, "w", encoding="utf-8", errors="replace", newline="\n") as f:
        if merged:
            f.write("\n".join(merged) + "\n")


def cleanup_files(file_list):
    for file_path in file_list:
        if not os.path.exists(file_path):
            continue
        try:
            os.remove(file_path)
            print(f"删除临时文件 {file_path}")
        except OSError as e:
            print(f"删除文件 {file_path} 时发生错误: {e}")


def run_subfinder():
    subfinder_exe = r".\tools\subfinder\subfinder.exe"
    input_file = r".\tools\subfinder\domains.txt"
    output_file = r".\tools\subfinder\subfinderok.txt"

    split_files = split_file(input_file, lines_per_file=20)
    if not split_files:
        return

    temp_outputs = []
    for index, current_file in enumerate(split_files, start=1):
        temp_output = f"{output_file}.{index}.tmp"
        temp_outputs.append(temp_output)
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError as e:
                print(f"清理旧临时结果 {temp_output} 失败: {e}")
        process_single_file(current_file, subfinder_exe, temp_output)
        try:
            os.remove(current_file)
            print(f"删除分割文件 {current_file}")
        except OSError as e:
            print(f"删除文件 {current_file} 时发生错误: {e}")

    merge_unique_files(temp_outputs, output_file)
    cleanup_files(temp_outputs)
    print(f"subfinder 合并完成，结果已保存到 {output_file}")


# 调用函数运行 subfinder
run_subfinder()
