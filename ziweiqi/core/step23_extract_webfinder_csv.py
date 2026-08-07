import csv
import os
import time

from encoding_utils import read_lines_guess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def extract_and_process():
    # 文件路径
    input_file = os.path.join(PROJECT_ROOT, "results", "output.csv")
    output_file = ".\\results\\tmp\\30_webfinderwebzz.txt"
    
    # 存储去重后的url
    urls = set()

    # 打开并读取output.csv文件
    rows = read_lines_guess(input_file)
    reader = csv.reader(rows)

    # 跳过标题行
    next(reader, None)

    for row in reader:
        if row:  # 确保不处理空行
            url = row[0].strip()  # 获取并去除前后空格
            if "://" in url and url:  # 过滤包含 '://' 的行
                urls.add(url)  # 使用set来去重

    # 将处理后的urls写入webfinderwebzz.txt
    with open(output_file, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")

    print(f"处理完成，结果已保存到 {output_file}")

if __name__ == "__main__":
    extract_and_process()
