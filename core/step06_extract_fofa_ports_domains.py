import os
import time
from encoding_utils import read_lines_guess

def extract_fifth_column():
    """提取 fofamap2.txt 中按竖线分割的第六列，并保存到 fofaport.txt"""
    input_file = r".\results\tmp\8_fofamap2.txt"
    output_file = r".\results\tmp\10_fofaport.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            ports = set()
            for line in lines:
                line = line.strip()  # 去除前后空格
                columns = line.split("|")  # 按竖线分割
                if len(columns) >= 6:
                    ports.add(columns[5].strip())  # 提取第六列

            with open(output_file, "w", encoding="utf-8") as f:
                for port in sorted(ports):
                    f.write(port + "\n")

            print(f"第五列内容已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def process_ports():
    """处理 fofaport.txt，去除前后空格，去除空白行和重复行，保存到 ports.txt"""
    input_file = r".\results\tmp\10_fofaport.txt"
    output_file = r".\results\tmp\11_ports.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            ports = set()
            for line in lines:
                line = line.strip()
                if line:  # 去除空白行
                    ports.add(line)

            with open(output_file, "w", encoding="utf-8") as f:
                for port in sorted(ports):
                    f.write(port + "\n")

            print(f"处理后的端口已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def process_domains():
    """处理 fofamap2.txt，提取第三列的子域名，去除前后空格，去除空白行和重复行，保存到 fofadomian2.txt"""
    input_file = r".\results\tmp\8_fofamap2.txt"
    output_file = r".\results\tmp\12_fofadomian2.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            domains = set()
            for line in lines:
                columns = line.split("|")
                if len(columns) >= 3:  # 确保有第三列
                    subdomain = columns[2].strip()  # 获取第三列并去除前后空格
                    if subdomain:  # 过滤掉空白子域名
                        domains.add(subdomain)

            with open(output_file, "w", encoding="utf-8") as f:
                for domain in sorted(domains):
                    f.write(domain + "\n")

            print(f"处理后的子域名已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def modify_domain_urls():
    """修改 fofadomian2.txt 中的域名，删除 https:// 和 http://，保存到 fofadomian3.txt"""
    input_file = r".\results\tmp\12_fofadomian2.txt"
    output_file = r".\results\tmp\13_fofadomian3.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            modified_domains = set()
            for line in lines:
                line = line.strip()
                if line.startswith("https://"):
                    line = line[8:]  # 删除 https://
                elif line.startswith("http://"):
                    line = line[7:]  # 删除 http://
                modified_domains.add(line)

            with open(output_file, "w", encoding="utf-8") as f:
                for domain in sorted(modified_domains):
                    f.write(domain + "\n")

            print(f"修改后的域名已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

def remove_after_colon():
    """处理 fofadomian3.txt 中的域名，删除 : 后面的内容，保存到 ziyuming2.txt"""
    input_file = r".\results\tmp\13_fofadomian3.txt"
    output_file = r".\results\tmp\14_ziyuming2.txt"

    if os.path.exists(input_file):
        try:
            lines = read_lines_guess(input_file)

            final_domains = set()
            for line in lines:
                line = line.strip()
                if ":" in line:
                    line = line.split(":")[0]  # 删除 : 后面的部分
                final_domains.add(line)

            with open(output_file, "w", encoding="utf-8") as f:
                for domain in sorted(final_domains):
                    f.write(domain + "\n")

            print(f"最终域名已保存到 {output_file}")
        except Exception as e:
            print(f"处理文件 {input_file} 时出错: {e}")
    else:
        print(f"{input_file} 不存在！")

if __name__ == "__main__":
    # 提取第五列并保存到 fofaport.txt
    extract_fifth_column()

    # 处理 ports.txt
    process_ports()

    # 处理 fofadomian.txt，保存到 fofadomian2.txt
    process_domains()

    # 修改域名中的 http:// 和 https://，保存到 fofadomian3.txt
    modify_domain_urls()

    # 删除 : 后面的内容并保存到 ziyuming2.txt
    remove_after_colon()
