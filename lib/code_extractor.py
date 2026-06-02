import re

def extract_code(filename: str) -> str:
    if not filename:
        return None
    # 1. 预清洗：移除常见网址广告域名以及后面跟随的 @ 等连接符
    clean_name = re.sub(r'(?i)(www\.)?[a-zA-Z0-9_-]+\.(com|net|org|xyz|club|asia|vip|cc|cn|co|me|tw|to|live|work|info|icu|online|shop)(@)?', '', filename)
    clean_name = re.sub(r'(?i)\[(1080p|720p|8k|4k|hhd|hd|中文字幕|字幕)\]', '', clean_name)
    clean_name = re.sub(r'(?i)[-_](ch|c|uncensored|diy)\b', '', clean_name)
    clean_name = re.sub(r'(?<=\d)[cC]\b', '', clean_name)
    
    # 2. 匹配 FC2 PPV
    fc2_match = re.search(r'(?i)\bfc2[-_]?ppv[-_]?(\d{5,7})\b', clean_name)
    if fc2_match:
        return f"FC2-PPV-{fc2_match.group(1)}"
        
    # 3. 匹配 T28
    t28_match = re.search(r'(?i)\bt28[-_]?(\d{3,4})\b', clean_name)
    if t28_match:
        return f"T28-{t28_match.group(1)}"

    # 4. 匹配标准 (字母)-(数字)
    std_match = re.search(r'(?i)\b([a-z]{2,5})[-_]?(\d{3,5})\b', clean_name)
    if std_match:
        prefix = std_match.group(1).upper()
        num = std_match.group(2)
        return f"{prefix}-{num}"
        
    return None
