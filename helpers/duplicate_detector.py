import os
import re

def find_existing_organized_folder(output_dir: str, code: str) -> str or None:
    """
    检索目标归档目录下是否已存在对应番号的归档文件夹。
    采用两级遍历（第一级：主演文件夹/未知演员；第二级：具体番号归档文件夹）。
    支持不区分大小写匹配，匹配模式为 "[番号] *"。
    """
    if not output_dir or not os.path.isdir(output_dir) or not code:
        return None
    
    code_escaped = re.escape(code.upper())
    # 匹配以 "[番号]" 开头的文件夹，防范子串误匹配
    pattern = re.compile(rf"^\[{code_escaped}\].*", re.IGNORECASE)
    
    try:
        # 第一层遍历 (如：主演子文件夹或直接是番号文件夹)
        for level1_entry in os.listdir(output_dir):
            level1_path = os.path.join(output_dir, level1_entry)
            if not os.path.isdir(level1_path):
                continue
            
            # 直接匹配（扁平化整理无演员子文件夹）
            if pattern.match(level1_entry):
                return level1_path
                
            # 第二层遍历 (演员/番号 结构)
            try:
                for level2_entry in os.listdir(level1_path):
                    level2_path = os.path.join(level1_path, level2_entry)
                    if os.path.isdir(level2_path) and pattern.match(level2_entry):
                        return level2_path
            except Exception:
                continue
    except Exception as e:
        print(f"检索重复归档文件夹异常: {e}")
        
    return None
