import os
import time
from encoding_utils import read_lines_guess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def process_fofamap_log():
    """处理 FofaMap/fofamap.log 文件"""
    log_file = os.path.join(PROJECT_ROOT, "tools", "FofaMap", "fofamap.log")
    output_file_cn = os.path.join(PROJECT_ROOT, "results", "tmp", "8_fofamap2.txt")  # CN的行
    output_file_http = os.path.join(PROJECT_ROOT, "results", "tmp", "9_fofamap3.txt")  # http的行

    # 检查 log 文件是否存在
    if os.path.exists(log_file):
        try:
            # 读取原始日志文件
            lines = read_lines_guess(log_file)

            # 用集合去重
            cn_lines = set()  # 用于存储包含 "CN" 的行
            http_lines = set()  # 用于存储包含 "http" 的行

            for line in lines:
                line = line.strip()  # 去除前后空格
                if "CN" in line:
                    cn_lines.add(line)
                if "http" in line:
                    http_lines.add(line)

            # 将包含 "CN" 的行保存到 8_fofamap2.txt
            with open(output_file_cn, "w", encoding="utf-8") as f:
                for line in cn_lines:
                    f.write(line + "\n")

            print(f"包含 'CN' 的行已保存到 {output_file_cn}")

            # 将包含 "http" 的行保存到 9_fofamap3.txt
            with open(output_file_http, "w", encoding="utf-8") as f:
                for line in http_lines:
                    f.write(line + "\n")

            print(f"包含 'http' 的行已保存到 {output_file_http}")

        except Exception as e:
            print(f"处理文件 {log_file} 时出错: {e}")
    else:
        print(f"{log_file} 不存在！")

if __name__ == "__main__":
    # 处理 FofaMap 日志文件，保存 CN 和 http 的行
    process_fofamap_log()
