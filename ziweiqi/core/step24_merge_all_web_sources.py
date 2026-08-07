import os
import shutil
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def merge_and_filter_files(output_file, *input_files):
    """合并多个文件，保留包含 '://' 的行，去空白行和重复行，保存到指定的输出文件。"""
    merged_lines = set()
    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"文件 {input_file} 不存在，跳过。")
            continue
        try:
            with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if "://" in line:  # 筛选条件
                    merged_lines.add(line)
        except Exception as e:
            print(f"读取文件 {input_file} 时发生错误: {e}")
            continue
    merged_lines = sorted(merged_lines)  # 可选排序
    output_dir = os.path.dirname(output_file)
    if output_dir:  # 如果路径不为空
        os.makedirs(output_dir, exist_ok=True)
    try:
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.writelines("\n".join(merged_lines) + "\n")
        print(f"合并后的内容已保存到 {output_file}")
    except Exception as e:
        print(f"保存到 {output_file} 时发生错误: {e}")


def copy_file(source, destination):
    """复制文件到目标路径。"""
    try:
        destination_dir = os.path.dirname(destination)
        if destination_dir:
            os.makedirs(destination_dir, exist_ok=True)
        shutil.copy(source, destination)
        print(f"文件 {source} 已成功复制到 {destination}")
    except Exception as e:
        print(f"复制文件 {source} 到 {destination} 时发生错误: {e}")


def merge_simple_files(output_file, *input_files):
    """合并多个文件的内容，去空白行和重复行，保存到指定的输出文件。"""
    merged_lines = set()
    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"文件 {input_file} 不存在，跳过。")
            continue
        try:
            with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line:  # 跳过空白行
                    merged_lines.add(line)
        except Exception as e:
            print(f"读取文件 {input_file} 时发生错误: {e}")
            continue
    merged_lines = sorted(merged_lines)  # 可选排序
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    try:
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.writelines("\n".join(merged_lines) + "\n")
        print(f"合并后的内容已保存到 {output_file}")
    except Exception as e:
        print(f"保存到 {output_file} 时发生错误: {e}")


def main():
    # 合并 fscanwebzz.txt、fofawebzz.txt 和 webfinderwebzz.txt
    input_files = [r".\results\tmp\29_fscanwebzz.txt", r".\results\tmp\18_fofawebzz.txt", r".\results\tmp\30_webfinderwebzz.txt"]
    output_file = r".\results\tmp\31_allwebzz.txt"
    merge_and_filter_files(output_file, *input_files)

    # 复制 webfinderwebzz.txt 到 tiquguanjianzi/mubiao.txt
    source_file = r".\results\tmp\31_allwebzz.txt"
    destination_file = os.path.join(PROJECT_ROOT, "tools", "tiquguanjianzi", "mubiao2.txt")
    copy_file(source_file, destination_file)

    # 合并 tools/fscan/ip.txt 和 tiquguanjianzi/guanjianzi.txt 到 tiquguanjianzi/guanjianzi2.txt
    ip_file = r".\tools\fscan\ip.txt"
    guanjianzi_file = os.path.join(r".\results\tmp\21_guanjian_1.txt")
    output_file = os.path.join(PROJECT_ROOT, "tools", "tiquguanjianzi", "guanjianzi2.txt")  # 保存到新的文件
    merge_simple_files(output_file, ip_file, guanjianzi_file)

if __name__ == "__main__":
    main()
