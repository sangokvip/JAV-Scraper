"""
文件名 → 番号提取。

规则表驱动：按优先级顺序尝试，命中即返回规范化番号。
新增命名体系时在 RULES 里加一条 (名称, 正则, 格式化函数) 即可。
"""
import re
from typing import Optional


def _format_standard(m: re.Match) -> str:
    prefix = m.group(1).upper()
    num = m.group(2)
    # DMM 零填充风格（ssis00123 = SSIS-123）：5 位以上且以 0 开头才去零，
    # 保住 ABP-001 这类真实带零番号
    if len(num) >= 5 and num.startswith('0'):
        num = num.lstrip('0') or '0'
        num = num.zfill(3)
    return f"{prefix}-{num}"


def _format_carib(m: re.Match) -> str:
    # 加勒比用连字符（123115-001），一本道/天然むすめ用下划线（010112_001），
    # 保留原分隔符供平台搜索
    sep = '-' if '-' in m.group(0) else '_'
    return f"{m.group(1)}{sep}{m.group(2)}"


# (规则名, 编译正则, 格式化函数)。顺序即优先级。
RULES = [
    ("fc2", re.compile(r'(?i)\bfc2[-_]?(?:ppv[-_]?)?(\d{5,8})\b'),
     lambda m: f"FC2-PPV-{m.group(1)}"),
    ("heydouga", re.compile(r'(?i)\bheydouga[-_]?(\d{4})[-_](\d{3,4})\b'),
     lambda m: f"HEYDOUGA-{m.group(1)}-{m.group(2)}"),
    ("t28", re.compile(r'(?i)\bt28[-_]?(\d{3,4})\b'),
     lambda m: f"T28-{m.group(1)}"),
    # Tokyo-Hot（n1234/k1234）：格式过短易误伤，只认文件名开头
    ("tokyo_hot", re.compile(r'(?i)^([nk])(\d{4})\b'),
     lambda m: f"{m.group(1).lower()}{m.group(2)}"),
    # 数字前缀素人系（259LUXU-1234 / 300MIUM-123 / 200GANA-2156）
    ("amateur", re.compile(r'(?i)\b(\d{3})([a-z]{2,6})[-_]?(\d{3,5})\b'),
     lambda m: f"{m.group(1)}{m.group(2).upper()}-{m.group(3)}"),
    # 加勒比/一本道/天然むすめ（MMDDYY-NNN / MMDDYY_NNN）
    ("carib_1pon", re.compile(r'\b(\d{6})[-_](\d{2,4})\b'), _format_carib),
    # 标准 字母-数字
    ("standard", re.compile(r'(?i)\b([a-z]{2,6})[-_]?(\d{3,5})\b'), _format_standard),
]


def extract_code(filename: str) -> Optional[str]:
    if not filename:
        return None
    # 预清洗：广告域名、分辨率标签、中文字幕/无码后缀
    clean_name = re.sub(r'(?i)(www\.)?[a-zA-Z0-9_-]+\.(com|net|org|xyz|club|asia|vip|cc|cn|co|me|tw|to|live|work|info|icu|online|shop)(@)?', '', filename)
    clean_name = re.sub(r'(?i)\[(1080p|720p|8k|4k|hhd|hd|中文字幕|字幕)\]', '', clean_name)
    clean_name = re.sub(r'(?i)[-_](ch|c|uncensored|diy)\b', '', clean_name)
    clean_name = re.sub(r'(?i)(?<=\d)(ch|c)\b', '', clean_name)
    clean_name = clean_name.strip()

    for _name, pattern, formatter in RULES:
        m = pattern.search(clean_name)
        if m:
            return formatter(m)
    return None
