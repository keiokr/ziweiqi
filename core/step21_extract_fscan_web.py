import os
import re
import time  # 导入 time 模块以支持延时
from urllib.parse import urlsplit
from console_utils import configure_stdio, safe_print

configure_stdio()

URL_RE = re.compile(r"https?://[^\s,;\"'<>]+", re.I)


def clean_url(url):
    """
    清洗 fscan 输出里的 URL token：
    - 去掉行尾标点和括号等噪声；
    - 只保留协议、主机、端口，即 scheme://host[:port]；
    - 丢弃 path/query/fragment，例如 /login_toLogin.do、/BSCTelmed/frontend/index。
    """
    url = str(url or "").strip()
    url = url.rstrip("，,。.;；:：)）]】}\"'")
    if not url:
        return ""

    try:
        parsed = urlsplit(url)
    except Exception:
        return url

    if parsed.scheme in ("http", "https") and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return url


def extract_urls_from_text(text):
    """从文本中按出现顺序提取并去重所有 http/https URL。"""
    seen = set()
    urls = []
    for match in URL_RE.finditer(text or ""):
        url = clean_url(match.group(0))
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def collect_fscan_input_files(tmp_dir=r".\results\tmp"):
    """
    收集所有 26_full_ok 开头的 fscan 原始/分批输出文件。
    会包含 26_full_ok.txt、26_full_ok.txt.N、26_full_ok.txt.N.tmp、26_full_ok_utf8.txt；
    会排除本脚本临时生成的 extract/all_prefix/current_logic 查看文件。
    """
    tmp_dir = os.path.abspath(tmp_dir)
    if not os.path.isdir(tmp_dir):
        return []

    exclude_keywords = ("extract_web", "all_prefix", "current_logic")
    files = []
    for name in os.listdir(tmp_dir):
        if not name.startswith("26_full_ok"):
            continue
        if any(keyword in name for keyword in exclude_keywords):
            continue
        path = os.path.join(tmp_dir, name)
        if os.path.isfile(path):
            files.append(path)

    def sort_key(path):
        name = os.path.basename(path)
        if name == "26_full_ok.txt":
            return (0, 0, name)
        match = re.search(r"\.(\d+)(?:\.tmp)?$", name)
        if match:
            return (1, int(match.group(1)), name)
        if name == "26_full_ok_utf8.txt":
            return (2, 0, name)
        return (3, 0, name)

    return sorted(files, key=sort_key)


def extract_urls_from_files(input_files):
    """从多个 fscan 文件中按文件顺序提取 URL，并全局去重。"""
    seen = set()
    urls = []
    stats = []
    for file_path in input_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                file_urls = extract_urls_from_text(f.read())
        except Exception as e:
            safe_print(f"读取 {file_path} 失败: {e}")
            continue

        new_count = 0
        for url in file_urls:
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            new_count += 1
        stats.append((file_path, len(file_urls), new_count))
    return urls, stats

# 读取文件并转换为 UTF-8 无 BOM 编码
def convert_to_utf8_no_bom(input_file, output_file):
    try:
        if not os.path.exists(input_file):
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                outfile.write("")
            safe_print(f"输入文件 {input_file} 不存在，已生成空文件 {output_file}，跳过 fscan Web 提取。")
            return False

        with open(input_file, 'r', encoding='utf-8', errors='replace') as infile:
            content = infile.read()

        with open(output_file, 'w', encoding='utf-8', newline='', errors='replace') as outfile:
            outfile.write(content)

        safe_print(f"文件成功转换并保存到 {output_file}")
        return True
    except Exception as e:
        safe_print(f"转换过程中发生错误: {e}")
        return False

# 提取并保留包含 :// 的行保存到 fscan22.txt
def extract_and_save_urls(input_file):
    with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    urls = [line.strip() for line in lines if "://" in line]
    urls = [url for url in urls if url.strip()]  # 去除空白行

    with open(r".\results\tmp\27_fscan22.txt", "w", encoding='utf-8') as out_file:
        out_file.writelines("\n".join(urls) + "\n")

    safe_print(f"包含 '://' 的原始行已保存到 fscan22.txt，共 {len(urls)} 行")

# 从 fscan22.txt 的所有行中提取 URL 保存到 fscan33.txt。
# 旧逻辑只提取 WebTitle 和 code: 之间的内容，会把 fscan 输出中的纯 URL 行全部丢掉。
def extract_webtitle_and_code(input_file):
    with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    extracted_content = extract_urls_from_text(content)

    with open(r".\results\tmp\28_fscan33.txt", "w", encoding="utf-8") as out_file:
        out_file.writelines("\n".join(extracted_content) + "\n")

    safe_print(f"已从 fscan 输出中提取 URL 到 fscan33.txt，共 {len(extracted_content)} 条")

# 继续处理 fscan33.txt 文件，清洗、去空白、按原顺序去重，保存到 fscanwebzz.txt
def process_fscan33_and_save():
    with open(r".\results\tmp\28_fscan33.txt", 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    seen = set()
    processed_lines = []

    for line in lines:
        line = clean_url(line)
        if not line or "://" not in line or line in seen:
            continue
        seen.add(line)
        processed_lines.append(line)

    with open(r".\results\tmp\29_fscanwebzz.txt", "w", encoding="utf-8") as out_file:
        out_file.writelines("\n".join(processed_lines) + "\n")

    safe_print(f"处理后的内容已保存到 fscanwebzz.txt，共 {len(processed_lines)} 条")

# 主程序调用
def main():
    input_file = r".\results\tmp\26_full_ok.txt"  # 原始输入文件路径
    output_file = r".\results\tmp\26_full_ok_utf8.txt"  # 转换后的文件路径

    # 转换文件编码为 UTF-8 无 BOM
    if not convert_to_utf8_no_bom(input_file, output_file):
        for empty_file in [
            r".\results\tmp\27_fscan22.txt",
            r".\results\tmp\28_fscan33.txt",
            r".\results\tmp\29_fscanwebzz.txt",
        ]:
            os.makedirs(os.path.dirname(empty_file), exist_ok=True)
            with open(empty_file, "w", encoding="utf-8"):
                pass
        return

    # 按 26_full_ok* 全部文件提取，避免只处理 26_full_ok.txt 单文件导致漏掉分批 tmp 结果。
    input_files = collect_fscan_input_files(r".\results\tmp")
    if input_files:
        all_urls, stats = extract_urls_from_files(input_files)
        for out_path in [
            r".\results\tmp\27_fscan22.txt",
            r".\results\tmp\28_fscan33.txt",
            r".\results\tmp\29_fscanwebzz.txt",
        ]:
            with open(out_path, "w", encoding="utf-8", newline="\n") as out_file:
                out_file.write("\n".join(all_urls) + ("\n" if all_urls else ""))

        safe_print("已按 26_full_ok* 全部文件提取 Web：")
        for file_path, extracted, new_count in stats:
            safe_print(f"  {os.path.basename(file_path)}: extracted={extracted}, merged_new={new_count}")
        safe_print(f"处理后的内容已保存到 fscanwebzz.txt，共 {len(all_urls)} 条")
        return

    # 提取包含 '://' 的行保存到 fscan22.txt
    extract_and_save_urls(output_file)

    # 从 fscan22.txt 提取 WebTitle 和 code: 之间的内容并保存到 fscan33.txt
    extract_webtitle_and_code(r".\results\tmp\27_fscan22.txt")

    # 处理 fscan33.txt 并保存到 fscanwebzz.txt
    process_fscan33_and_save()

if __name__ == "__main__":
    main()
