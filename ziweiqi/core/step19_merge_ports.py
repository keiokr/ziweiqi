import os
from encoding_utils import read_lines_guess

def process_ports_file():
    """处理端口文件，保存为 fscan 可识别的逗号分隔格式，且不保留尾逗号。"""
    try:
        # 检查输入文件是否存在
        input_file = '.\\results\\tmp\\11_ports.txt'
        if not os.path.exists(input_file):
            print(f"{input_file} 文件未找到，无法处理端口。")
            return
        
        # 读取输入文件内容
        ports = [line.strip().strip(",") for line in read_lines_guess(input_file) if line.strip().strip(",")]

        # 检查是否读取到端口
        if not ports:
            print("没有读取到有效的端口数据。")
            return

        # 去重并添加逗号，避免生成 80,443, 这种尾逗号格式
        ports = list(dict.fromkeys(ports))
        ports_str = ",".join(ports)

        # 确保输出目录存在
        output_dir = '.\\tools\\fscan'
        os.makedirs(output_dir, exist_ok=True)

        # 写入文件
        output_file = os.path.join(output_dir, 'ports.txt')
        with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(ports_str + "\n")

        print(f"端口已处理并保存到 {output_file}")

    except Exception as e:
        print(f"处理文件时发生错误: {e}")

# 调用函数
process_ports_file()
