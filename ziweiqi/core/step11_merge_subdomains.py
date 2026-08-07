import os
import subprocess
import time
import shutil
import glob


def process_allok_and_save():
    """处理并将 tools\\alldomainV4\\OneForAll\\OneForAllok.txt、
       tools\\subfinder\\subfinderok.txt 和 tools\\ksubdomain\\ksubok.txt 文件的内容
       追加到 tmp\19_ziyming3.txt 文件。"""
    
    # 文件路径
    files_to_process = [
        r".\tools\OneForAll\OneForAllok.txt",
        r".\tools\subfinder\subfinderok.txt",
        r".\tools\ksubdomain\ksubok.txt"
    ]
    
    output_file = r".\results\tmp\19_ziyming3.txt"
    
    try:
        # 打开输出文件以追加内容
        with open(output_file, "a", encoding="utf-8") as out_f:
            # 遍历需要处理的文件
            for file_path in files_to_process:
                if os.path.exists(file_path):
                    try:
                        # 打开并读取每个文件
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        
                        valid_lines = []
                        for line in lines:
                            # 分割每一行，去除首尾空格
                            parts = line.strip().split()
                            # 检查是否包含 '.'（域名或IP）
                            for part in parts:
                                if "." in part:
                                    valid_lines.append(part)

                        # 将有效的域名或IP追加到 output_file
                        for line in sorted(set(valid_lines)):
                            out_f.write(line + "\n")
                        print(f"已处理并将有效域名保存到 {output_file}")
                    
                    except Exception as e:
                        print(f"处理文件 {file_path} 时出错: {e}")
                else:
                    print(f"{file_path} 不存在！")
    
    except Exception as e:
        print(f"无法打开输出文件 {output_file} 进行追加操作: {e}")

if __name__ == "__main__":
    # 处理并追加文件内容
    process_allok_and_save()

