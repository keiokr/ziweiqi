import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir, os.pardir))

# 读取 guanjianzi.txt 文件中的关键字列表  
guanjianzi_path = os.path.join(BASE_DIR, "guanjianzi.txt")
with open(guanjianzi_path, 'r', encoding='utf-8') as gjz_file:
    keywords = gjz_file.read().splitlines()

# 初始化一个空集合来存储已匹配的行的标识符（假设每行都是唯一的）  
matched_lines_set = set()

# 初始化一个空列表来存储匹配的行（仅用于写入文件时保持顺序）  
matching_lines = []

# 读取 mubiao.txt 文件并匹配关键字
mubiao_path = os.path.join(BASE_DIR, "mubiao.txt")
with open(mubiao_path, 'r', encoding='utf-8') as chuli_file:
    for line in chuli_file:
        # 去除行首尾的空白字符
        line_stripped = line.strip()
        
        # 遍历关键字列表，检查当前行是否以任何关键字结束
        for keyword in keywords:
            if line_stripped.endswith(keyword):
                # 如果找到匹配项且之前未匹配过（即不在集合中）
                if line_stripped not in matched_lines_set:
                    # 将该行添加到匹配行列表中
                    matching_lines.append(line)
                    # 将行的标识符（去除换行符的行内容）添加到集合中
                    matched_lines_set.add(line_stripped)
                    break  # 找到匹配项后跳出内层循环

# 保存匹配的行到 jieguo.txt 文件
output_path = os.path.join(PROJECT_ROOT, "results", "tmp", "22_jieguo1.txt")
with open(output_path, 'w', encoding='utf-8') as jieguo_file:
    jieguo_file.writelines(matching_lines)

print("匹配的行已保存到 22_jieguo1.txt 文件中。")
