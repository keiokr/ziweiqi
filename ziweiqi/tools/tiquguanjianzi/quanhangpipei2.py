import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir, os.pardir))


def read_lines_guess(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16"):
        try:
            return raw.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").splitlines()

# 读取guanjianzi.txt文件中的关键字列表
gjz_file_path = os.path.join(BASE_DIR, "guanjianzi2.txt")
keywords = set(read_lines_guess(gjz_file_path))  # 使用set以提高查找效率

# 初始化一个空列表来存储匹配的行
matching_lines = []

# 打开并处理mubiao.txt文件
mubiao_file_path = os.path.join(BASE_DIR, "mubiao2.txt")
for line in read_lines_guess(mubiao_file_path):
    # 遍历关键字集合，检查当前行是否包含任何关键字
    if any(keyword in line for keyword in keywords):
        # 如果找到匹配项，将该行添加到匹配行列表中
        matching_lines.append(line + "\n")

# 将匹配的行写入jieguo.txt文件，并确保每行后都有换行符
output_file_path = os.path.join(PROJECT_ROOT, "results", "tmp", "32_jieguo2.txt")
with open(output_file_path, 'w', encoding='utf-8', errors='replace', newline='\n') as jieguo_file:
    jieguo_file.writelines(matching_lines)
    # 如果matching_lines不为空，添加一个额外的换行符以确保文件最后也有换行
    if matching_lines:
        jieguo_file.write('\n')

print("包含关键字的行已保存到jieguo2.txt文件中。")

# 等待3秒钟
time.sleep(3)
