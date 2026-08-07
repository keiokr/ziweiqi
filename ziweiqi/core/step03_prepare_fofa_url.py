import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def process_domains():
    """将 domains.txt 内容复制到 FofaMap-1.1.3/url.txt 并在每行前后添加字符串"""
    input_file = os.path.join(PROJECT_ROOT, "results", "tmp", "7_domains.txt")
    output_file = os.path.join(PROJECT_ROOT, "tools", "FofaMap", "url.txt")
    
    # 检查 domains.txt 是否存在
    if not os.path.exists(input_file):
        print(f"文件 {input_file} 不存在！")
        return

    # 检查 FofaMap 目录是否存在
    if not os.path.exists(os.path.dirname(output_file)):
        print(f"目录 FofaMap不存在！")
        return
    
    # 读取 domains.txt 内容，忽略无法编码的字符
    try:
        with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"读取文件 {input_file} 时出错: {e}")
        return

    # 处理每一行并添加前后缀
    processed_lines = [f'domain="{line.strip()}"\n' for line in lines if line.strip()]

    # 写入 FofaMap/url.txt 文件
    try:
        with open(output_file, 'w', encoding='utf-8', errors='replace') as f:
            f.writelines(processed_lines)
        print(f"域名已处理并保存到 {output_file}")
    except Exception as e:
        print(f"写入文件 {output_file} 时出错: {e}")

if __name__ == "__main__":
    process_domains()
