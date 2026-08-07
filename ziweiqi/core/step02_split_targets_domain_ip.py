import os
import re
import shutil

def is_ip(line):
    # 改进的IP地址正则匹配（IPv4）
    ip_pattern = r'^\s*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s*$'
    return re.match(ip_pattern, line) is not None

def process_file():
    # 确保tmp目录存在
    if not os.path.exists('results/tmp'):
        os.makedirs('results/tmp', exist_ok=True)
    
    ip_lines = []
    non_ip_lines = []
    
    # 尝试用不同编码读取文件（优先尝试utf-8-sig处理BOM）
    encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'utf-16']
    
    content = None
    for encoding in encodings:
        try:
            with open('scanIPAndDomain.txt', 'r', encoding=encoding) as f:
                content = [line.strip() for line in f if line.strip()]
            break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        print("无法读取文件，请检查文件编码")
        return
    
    for line in content:
        if is_ip(line):
            ip_lines.append(line + '\n')
        else:
            non_ip_lines.append(line + '\n')
    
    # 写入文件时统一使用utf-8编码
    try:
        with open('results/tmp/6_ip.txt', 'w', encoding='utf-8') as f:
            f.writelines(ip_lines)
        
        with open('results/tmp/1_enscangenyuming.txt', 'w', encoding='utf-8') as f:
            f.writelines(non_ip_lines)
        
        # 复制文件
        shutil.copy2('results/tmp/1_enscangenyuming.txt', 'results/tmp/5_alldomains.txt')
        shutil.copy2('results/tmp/1_enscangenyuming.txt', 'results/tmp/7_domains.txt')
        
        print("处理完成！")
    except Exception as e:
        print(f"写入文件时出错: {str(e)}")

if __name__ == '__main__':
    process_file()
