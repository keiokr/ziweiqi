import os
import time
from encoding_utils import read_lines_guess

def extract_second_column():
    """提取 fofamap3.txt 按竖线分割的第三列，并保存到 fofaweb1.txt"""
    input_file = r".\results\tmp\9_fofamap3.txt"
    output_file = r".\results\tmp\15_fofaweb1.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            second_column = set()
            for line in lines:
                line = line.strip()
                columns = line.split("|")  # 按竖线分割
                if len(columns) >= 3:
                    second_column.add(columns[2])  # 提取第三列

            with open(output_file, "w", encoding="utf-8") as f:
                for item in sorted(second_column):
                    f.write(item + "\n")

            print(f"第二列内容已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def process_fofaweb1():
    """处理 fofaweb1.txt，去除前后空格，去除空白行和重复行，保存到 fofaweb2.txt"""
    input_file = r".\results\tmp\15_fofaweb1.txt"
    output_file = r".\results\tmp\16_fofaweb2.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            fofaweb2 = set()
            for line in lines:
                line = line.strip()
                if line:  # 去除空白行
                    fofaweb2.add(line)

            with open(output_file, "w", encoding="utf-8") as f:
                for item in sorted(fofaweb2):
                    f.write(item + "\n")

            print(f"处理后的内容已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def extract_with_colon():
    """从 fofaweb2.txt 中提取包含 : 的行并保存到 fofaweb3.txt"""
    input_file = r".\results\tmp\16_fofaweb2.txt"
    output_file = r".\results\tmp\17_fofaweb3.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            fofaweb3 = set()
            for line in lines:
                line = line.strip()
                if ":" in line:
                    fofaweb3.add(line)

            with open(output_file, "w", encoding="utf-8") as f:
                for item in sorted(fofaweb3):
                    f.write(item + "\n")

            print(f"提取包含 : 的行已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def add_http_if_missing():
    """检查 fofaweb3.txt 中的行，如果没有 https://，则添加 http://"""
    input_file = r".\results\tmp\17_fofaweb3.txt"
    output_file = r".\results\tmp\18_fofawebzz.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            modified_lines = []
            for line in lines:
                line = line.strip()
                if not line.startswith("https://"):
                    line = "http://" + line  # 如果没有 https://，添加 http://
                modified_lines.append(line)

            with open(output_file, "w", encoding="utf-8") as f:
                for item in sorted(modified_lines):
                    f.write(item + "\n")

            print(f"修改后的内容已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

if __name__ == "__main__":
    # 提取第二列并保存到 fofaweb1.txt
    extract_second_column()

    # 处理 fofaweb1.txt，保存到 fofaweb2.txt
    process_fofaweb1()

    # 提取包含 : 的行并保存到 fofaweb3.txt
    extract_with_colon()

    # 如果没有 https://，则添加 http://，保存到 fofawebzz.txt
    add_http_if_missing()
