import os
import time
from encoding_utils import read_lines_guess

def merge_and_remove_duplicates():
    """合并 ziyuming1.txt 和 ziyuming2.txt，去重并保存到 ziyuming_combined.txt"""
    file1_path = r".\results\tmp\14_ziyuming2.txt"  # 使用绝对路径
    file2_path = r".\results\tmp\19_ziyming3.txt"  # 使用绝对路径
    output_file = r".\results\tmp\20_ziyuming_all.txt"  # 使用绝对路径

    if os.path.exists(file1_path) and os.path.exists(file2_path):
        try:
            # 读取两个文件的内容
            lines1 = read_lines_guess(file1_path)
            lines2 = read_lines_guess(file2_path)

            # 合并两个文件的内容并去重
            combined_lines = set(line.strip() for line in lines1 + lines2)  # 去除重复并去除前后空格

            # 保存去重后的内容到新文件
            with open(output_file, "w", encoding="utf-8") as f:
                for line in sorted(combined_lines):
                    f.write(line + "\n")

            print(f"合并去重后的内容已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件时出错: {e}")
    else:
        print("文件 14_ziyuming2.txt 或 19_ziyming3.txt 不存在！")

if __name__ == "__main__":
    merge_and_remove_duplicates()
