import os
import re
import sys

# Windows 保留设备名：即使加了扩展名（如 "CON.txt"）也不能作为文件/目录名
_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Windows 经典 MAX_PATH 为 260；留出文件名（如 ABC-123-CD1.mp4 / extrafanart/fanart10.jpg）的余量
_WIN_MAX_DIR_LEN = 200


def clean_path_component(val: str) -> str:
    """
    把一个路径分量清洗成三大平台都合法的目录名：
    - 替换 \ / : * ? " < > | 与控制字符（Windows 全部非法，POSIX 至少 / 非法）
    - 去掉首尾空白与结尾的 . （Windows 会静默截掉结尾的点/空格，导致路径不一致）
    - 命中 Windows 保留设备名时加下划线前缀
    """
    val = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(val))
    val = val.strip().rstrip(". ")
    if val.split(".")[0].upper() in _WIN_RESERVED:
        val = "_" + val
    return val

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
    
    # 单趟替换全部命中的变量：逐 key 替换会在替换第一个后直接返回，
    # {code title} 这类组合占位符只换一半；单趟 alternation 也不会扫到已替换的值
    keys_pattern = re.compile('|'.join(re.escape(k) for k in replacements), re.IGNORECASE)

    def replace_placeholder(match):
        inner = match.group(1)
        if not keys_pattern.search(inner):
            return match.group(0)
        return keys_pattern.sub(lambda m: replacements[m.group(0).lower()], inner)
        
    path_rel = re.sub(r'\{([^{}]+)\}', replace_placeholder, template)
        
    # 分割相对路径，规范化并防范路径穿越 (..)
    parts = []
    # 兼容斜杠和反斜杠分割
    split_parts = re.split(r'[\\/]', path_rel)
    for p in split_parts:
        # 模板里用户手写的字面量（如 "我的收藏."）同样要过一遍清洗，
        # 否则 Windows 上会得到与预期不一致的目录名
        p_clean = clean_path_component(p)
        if not p_clean or p_clean in ('.', '..'):
            continue
        parts.append(p_clean)
        
    if not parts:
        parts = [f"[{code_clean}] {title_clean}"]
        
    # 最后一级目录进行最大安全长度截断，防止超出系统限制 (建议截断至 80 字符)
    parts[-1] = parts[-1][:80].rstrip(". ").strip()

    # 拼接并生成最终绝对路径
    target_folder = os.path.abspath(os.path.join(output_dir, *parts))

    # Windows 未开启长路径支持时整条路径不能超过 260 字符；
    # 保存路径本身很深（如 D:\影片库\整理\...）时继续压缩最后一级目录
    if sys.platform == "win32" and len(target_folder) > _WIN_MAX_DIR_LEN:
        overflow = len(target_folder) - _WIN_MAX_DIR_LEN
        keep = max(len(parts[-1]) - overflow, len(code_clean) + 2)
        parts[-1] = parts[-1][:keep].rstrip(". ").strip()
        target_folder = os.path.abspath(os.path.join(output_dir, *parts))
    return target_folder
