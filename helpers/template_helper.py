import os
import re

def format_target_path(template: str, output_dir: str, code: str, detail: dict) -> str:
    """
    根据用户定义的分级命名模板，格式化出归档文件夹的目标物理绝对路径。
    模板支持变量：
      - {actor}: 影片第一主演。若无，退化为 "未知演员"
      - {studio}: 片商（依次取 series, maker, publisher, producer）。若无，退化为 "未知片商"
      - {code}: 影片清洗后的番号
      - {title}: 影片的原始中文标题
      - {year}: 影片发行年份（从发行日期中智能匹配前4位数字）
      - {date}: 影片发行日期（格式 YYYY-MM-DD）
    """
    if not template:
        template = "{actor}/{[code]} {title}"
        
    # 提取演员
    actors = detail.get("actors", [])
    actor = actors[0].strip() if actors else "未知演员"
    
    # 提取片商
    studio = detail.get("series", "") or detail.get("maker", "") or detail.get("publisher", "") or detail.get("producer", "") or "未知片商"
    studio = studio.strip()
    
    # 提取标题与日期
    title = detail.get("title", "").strip()
    date = detail.get("date", "").strip()
    
    # 提取年份
    year = "未知年份"
    if date:
        match = re.search(r'\b\d{4}\b', date)
        if match:
            year = match.group(0)
            
    # 文件系统非法路径字符清洗
    def clean_path_component(val: str) -> str:
        for char in r'\/:*?"<>|':
            val = val.replace(char, " ")
        return val.strip()
        
    actor_clean = clean_path_component(actor) or "未知演员"
    studio_clean = clean_path_component(studio) or "未知片商"
    title_clean = clean_path_component(title) or "未知标题"
    code_clean = clean_path_component(code) or "未知番号"
    year_clean = clean_path_component(year) or "未知年份"
    date_clean = clean_path_component(date) or "未知日期"
    
    # 执行模板变量替换 (忽略大小写，且支持花括号内的修饰符如 {[code]})
    replacements = {
        "actor": actor_clean,
        "studio": studio_clean,
        "code": code_clean,
        "title": title_clean,
        "year": year_clean,
        "date": date_clean
    }
    
    def replace_placeholder(match):
        inner = match.group(1)
        for key, val in replacements.items():
            pattern = re.compile(re.escape(key), re.IGNORECASE)
            if pattern.search(inner):
                return pattern.sub(val, inner)
        return match.group(0)
        
    path_rel = re.sub(r'\{([^{}]+)\}', replace_placeholder, template)
        
    # 分割相对路径，规范化并防范路径穿越 (..)
    parts = []
    # 兼容斜杠和反斜杠分割
    split_parts = re.split(r'[\\/]', path_rel)
    for p in split_parts:
        p_clean = p.strip()
        if not p_clean or p_clean in ('.', '..'):
            continue
        parts.append(p_clean)
        
    if not parts:
        parts = [f"[{code_clean}] {title_clean}"]
        
    # 最后一级目录进行最大安全长度截断，防止超出系统限制 (建议截断至 80 字符)
    parts[-1] = parts[-1][:80].strip()
    
    # 拼接并生成最终绝对路径
    target_folder = os.path.abspath(os.path.join(output_dir, *parts))
    return target_folder
