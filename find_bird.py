import pandas as pd
import os

def find_missing_birds(excel_path, log_path, output_path):
    print("开始读取文件...")
    
    # 1. 读取 Excel 文件中的鸟类名字
    try:
        # 读取Excel，指定使用第一列
        df = pd.read_excel(excel_path)
        
        # 提取 'bird_name' 列。使用 .dropna() 去除空行，.astype(str) 转为字符串，.str.strip() 去除首尾空格防止匹配失败
        if 'bird_name' in df.columns:
            excel_birds = set(df['bird_name'].dropna().astype(str).str.strip())
        else:
            # 如果没找到列名，默认使用第一列
            excel_birds = set(df.iloc[:, 0].dropna().astype(str).str.strip())
            
        print(f"Excel文件中共读取到 {len(excel_birds)} 种鸟类。")
    except Exception as e:
        print(f"读取 Excel 文件时出错: {e}")
        return

    # 2. 读取 log 文件中已处理的鸟类名字
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            # 逐行读取，并去除前后的空格和换行符，忽略空行
            log_birds = set(line.strip() for line in f if line.strip())
        print(f"Log文件中共读取到 {len(log_birds)} 种已处理的鸟类。")
    except Exception as e:
        print(f"读取 Log 文件时出错: {e}")
        return

    # 3. 找出 Excel 中有，但是 Log 中没有的鸟类（集合差集）
    missing_birds = excel_birds - log_birds

    # 4. 将缺失的鸟类名字写入第三个文件
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for bird in sorted(missing_birds): # 排序后写入，更整齐
                f.write(f"{bird}\n")
                
        print(f"对比完成！")
        print(f"共发现 {len(missing_birds)} 种未处理（缺失）的鸟类。")
        print(f"缺失名单已保存至: {output_path}")
        
    except Exception as e:
        print(f"写入输出文件时出错: {e}")

# ================= 使用示例 =================
if __name__ == "__main__":
    # 文件路径定义
    excel_file = r"C:\Users\Xiao\Desktop\鸟类文本库\文本知识库-更新.xlsx"
    log_file = r"C:\Users\Xiao\Desktop\鸟类文本库\题目生成脚本\Generation\processed_birds.log"
    # 第三个文件：输出缺失鸟类的文件路径
    output_file = r"C:\Users\Xiao\Desktop\鸟类文本库\题目生成脚本\Generation\missing_birds.txt"
    
    # 执行函数
    find_missing_birds(excel_file, log_file, output_file)