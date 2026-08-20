import os
from encoding_utils import read_lines_guess
from fscan_utils import normalize_ports_text

def process_ports_file():
    """处理端口文件，最终校验/去重后保存为 fscan 可识别的逗号分隔格式。"""
    try:
        # 检查输入文件是否存在
        input_file = '.\\results\\tmp\\11_ports.txt'
        if not os.path.exists(input_file):
            print(f"{input_file} 文件未找到，无法处理端口。")
            return
        
        # 读取输入文件内容，并在写入 fscan 前做最终端口格式校验和去重。
        ports, invalid_ports, duplicate_count = normalize_ports_text("\n".join(read_lines_guess(input_file)))

        # 检查是否读取到端口
        if not ports:
            print("没有读取到有效的端口数据。")
            return

        ports_str = ",".join(ports)

        # 确保输出目录存在
        output_dir = '.\\tools\\fscan'
        os.makedirs(output_dir, exist_ok=True)

        # 写入文件
        output_file = os.path.join(output_dir, 'ports.txt')
        with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(ports_str + "\n")

        print(
            f"端口已处理并保存到 {output_file}；"
            f"fscan 最终端口项: {len(ports)}，"
            f"去重: {duplicate_count}，非法: {len(invalid_ports)}"
        )
        if invalid_ports:
            print(f"已跳过非法端口示例: {', '.join(invalid_ports[:10])}")

    except Exception as e:
        print(f"处理文件时发生错误: {e}")

# 调用函数
process_ports_file()
