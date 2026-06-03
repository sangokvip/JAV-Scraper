"""
JAVDB API 配置文件示例
复制此文件为 config.py 并填入你的账号信息
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 输出目录配置
OUTPUT_DIR = {
    'root': PROJECT_ROOT / 'output',
    'csv': PROJECT_ROOT / 'output' / 'csv',
    'json': PROJECT_ROOT / 'output' / 'json',
    'images': PROJECT_ROOT / 'output' / 'images',
    'magnets': PROJECT_ROOT / 'output' / 'magnets',
}

# 确保输出目录存在
for dir_path in OUTPUT_DIR.values():
    dir_path.mkdir(parents=True, exist_ok=True)

# 默认输出文件名
DEFAULT_OUTPUT = {
    'csv': 'result.csv',
    'json': 'result.json',
    'actor': 'actor_works.csv',
    'tag': 'tag_works.csv',
    'magnet': 'magnets.txt',
}

# JAVDB 配置
JAVDB = {
    # 域名列表
    'domains': [
        'javdb.com',
        'javdb570.com',
    ],
    # 默认域名索引
    'default_domain_index': 0,
    # 请求超时（秒）
    'timeout': 8,
    # 重试次数
    'retry_times': 1,
    # 请求间隔（秒）
    'sleep_time': 2,
    # 每页作品数
    'page_size': 40,
    # 最大爬取页数
    'max_pages': 10,
}

# 请求头配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Cookie 文件
COOKIE_FILE = 'cookies.json'

# 登录配置 - 请填入你的账号信息
LOGIN = {
    'username': 'YOUR_USERNAME',  # 你的用户名
    'password': 'YOUR_PASSWORD',  # 你的密码
}

# CSV 编码
CSV_ENCODING = 'utf-8-sig'

# JSON 配置
JSON_INDENT = 2
JSON_ENSURE_ASCII = False

# 日志配置
LOG_LEVEL = 'INFO'
LOG_FORMAT = '[%(asctime)s] %(levelname)s: %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
