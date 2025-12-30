import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import json
import os
import sys
import glob
import datetime # Added for timestamp

def resource_path(relative_path):
    """ 获取资源的绝对路径，无论是开发环境还是PyInstaller环境. """
    try:
        # PyInstaller 创建一个临时文件夹，并把路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def load_config(config_path="config.json"):
    """从JSON文件加载配置"""
    print(f"正在加载配置文件: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_receipt_boundaries(page, config):

    """在一页中根据锚点文本查找所有回单的垂直边界"""

    height = page.height

    header_anchors = config.get("header_anchors", [])

    footer_anchors = config.get("footer_anchors", [])

    margin_top = config.get("crop_margins", {}).get("top", 20)

    

    words = page.extract_words(use_text_flow=True)

    

    # 1. 找到所有回单标题的 Y 坐标 (Top 坐标)

    headers_y = []

    for anchor in header_anchors:

        for w in words:

            if anchor in w['text']:

                if not headers_y or all(abs(w['top'] - hy) > 20 for hy in headers_y):

                    headers_y.append(w['top'])

        if headers_y and anchor == header_anchors[0]:

            break

    headers_y.sort()



    # 2. 找到所有页脚的 Y 坐标 (bottom 坐标)

    footers = []

    if footer_anchors:

        for anchor in footer_anchors:

            for w in words:

                if anchor in w['text']:

                    footers.append(w)



    # 3. 如果没有找到任何锚点，将整页作为一个回单处理

    if not headers_y:

        print("  - 警告: 未在本页找到回单锚点，将整页视为一张回单。")

        return [(0, height)]



    print(f"  - 发现 {len(headers_y)} 个标题锚点，尝试切分为 {len(headers_y)} 张回单。")



    # 4. 根据标题和页脚创建裁剪区域

    boundaries = []

    for i, header_y in enumerate(headers_y):

        y_start = max(0, header_y - margin_top)

        y_end = height # 默认结束点是页面底部



        # 优先使用页脚来确定结束点

        found_footer = False

        if footers:

            # 寻找在当前标题下方的第一个页脚

            possible_footers = sorted([f for f in footers if f['top'] > header_y], key=lambda x: x['top'])

            if possible_footers:

                # 找到页脚，将结束点设在页脚文字下方一点

                y_end = possible_footers[0]['bottom'] + 5 

                found_footer = True



        # 如果没有找到对应的页脚，则回退到使用下一个标题作为结束点

        if not found_footer:

            if i + 1 < len(headers_y):

                y_end = headers_y[i+1] - margin_top

        

        boundaries.append((y_start, y_end))



    return boundaries

def classify_receipt_text(text, keywords_config):
    """根据文本内容和关键字配置进行分类"""
    text_clean = text.replace("\n", "").replace(" ", "")
    for category, keywords in keywords_config.items():
        for key in keywords:
            if key in text_clean:
                return category
    return "others"

def write_sorted_pdf(reader, categorized_receipts, output_path, order):
    """将分类并裁剪好的回单写入新的PDF文件"""
    writer = PdfWriter()
    count = 0
    
    for category in order:
        if category not in categorized_receipts:
            continue
            
        items = categorized_receipts[category]
        for item in items:
            # 获取原始页面
            original_page = reader.pages[item['page_index']]
            
            # 添加页面并立即获取其引用以进行修改
            writer.add_page(original_page)
            new_page = writer.pages[-1]
            
            # 设置裁剪框 (Left, Bottom, Right, Top)
            rect = item['rect']
            new_page.cropbox.lower_left = (rect[0], rect[1])
            new_page.cropbox.upper_right = (rect[2], rect[3])
            # 同步 mediabox, 否则在某些阅读器中可能无法正确显示裁剪
            new_page.mediabox.lower_left = (rect[0], rect[1])
            new_page.mediabox.upper_right = (rect[2], rect[3])
            
            count += 1
            
    with open(output_path, "wb") as f:
        writer.write(f)
        
    print(f"\n处理完成！共导出 {count} 张独立回单。" )
    print(f"文件已保存为: {output_path}")

def sort_bank_receipts(input_path, output_path, config):
    """主函数，负责协调整个PDF处理流程"""
    print(f"正在处理文件: {input_path} ...")
    
    reader = PdfReader(input_path)
    
    # 初始化分类存储
    keywords_config = config.get("category_keywords", {})
    categories = {cat: [] for cat in keywords_config.keys()}
    categories["others"] = []

    with pdfplumber.open(input_path) as pdf:
        total_pages = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            print(f"\n- 正在分析第 {i+1}/{total_pages} 页...")
            width, height = page.width, page.height
            
            boundaries = find_receipt_boundaries(page, config)
            
            for y_start, y_end in boundaries:
                # 1. 提取并分类
                crop_box = (0, y_start, width, y_end)
                cropped_section = page.crop(crop_box)
                text_content = cropped_section.extract_text(x_tolerance=2) or ""
                
                category = classify_receipt_text(text_content, keywords_config)
                
                # 2. 存储裁剪信息 (使用PyPDF2坐标系)
                # 转换坐标: PyPDF2_Y = PageHeight - Plumber_Y
                pdf_y_top = height - y_start
                pdf_y_bottom = height - y_end
                
                categories[category].append({
                    "page_index": i,
                    "rect": (0, pdf_y_bottom, width, pdf_y_top) # Left, Bottom, Right, Top
                })
                print(f"  - 发现一张回单，分类为: '{category}'")

    # 3. 写入文件
    output_order = config.get("output_order", list(categories.keys()))
    write_sorted_pdf(reader, categories, output_path, output_order)
    
    # 4. 打印总结
    print("\n分类统计:")
    for category in output_order:
        if category in categories:
            print(f"  - {category}: {len(categories[category])} 张")


if __name__ == "__main__":
    # --- 配置 ---
    config_path = resource_path("config.json")
    
    # --- 输入文件处理 ---
    input_file_path = None
    
    # 1. 尝试从命令行参数获取输入文件
    if len(sys.argv) > 1:
        input_file_path = sys.argv[1]
    
    if not input_file_path:
        # 2. 如果没有命令行参数，列出当前目录下的PDF文件供用户选择
        pdf_files = glob.glob("*.pdf")
        # 排除可能存在的已排序文件
        pdf_files = [f for f in pdf_files if not f.endswith('_sorted.pdf')]

        if pdf_files:
            print("\n当前目录下的PDF文件：")
            for i, pdf_file in enumerate(pdf_files):
                print(f"  [{i+1}] {pdf_file}")
            
            while True:
                choice = input("请选择要处理的PDF文件编号，或直接输入文件名：").strip()
                if not choice:
                    print("请输入一个选项。")
                    continue
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(pdf_files):
                        input_file_path = pdf_files[idx]
                        break
                    else:
                        print("无效的编号，请重新输入。")
                else:
                    input_file_path = choice
                    break
        else:
            # 3. 如果没有找到PDF文件，提示用户手动输入
            input_file_path = input("当前目录下没有可供处理的PDF文件。请输入要处理的PDF文件名：").strip()
            if not input_file_path:
                print("未指定输入文件，程序退出。")
                sys.exit(1)

    # --- 动态生成输出文件名 ---
    base_name = os.path.splitext(os.path.basename(input_file_path))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file_path = f"{base_name}_sorted_{timestamp}.pdf"
    print(f"输出文件将保存为: {output_file_path}")

    # --- 执行 ---
    try:
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"错误：找不到输入文件 '{input_file_path}'，请确认文件名正确。")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"错误：找不到配置文件 '{config_path}'，请确认文件存在。")
            
        app_config = load_config(config_path)
        sort_bank_receipts(input_file_path, output_file_path, app_config)
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\n错误: {e}")
    except Exception as e:
        print(f"\n发生未知错误: {e}")
