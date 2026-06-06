"""
JAVDB API 配置文件示例
复制此文件为 config.py 并填入你的账号信息
"""

import os
import sys
from pathlib import Path

# ============================================================================
# 路径分层体系 (适配 PyInstaller 打包与开发态)
# ============================================================================
#
# BUNDLE_DIR  — 只读资源目录 (cookies.json, lib/, gui/, third_party_config.json)
#               打包态: sys._MEIPASS (macOS: .app/Contents/Resources/)
#               开发态: 项目根目录
#
# DATA_DIR    — 可写用户数据目录 (settings_backup, tasks_backup, output/)
#               打包态: .app 所在目录 (即 dist/)
#               开发态: 项目根目录
#
# PROJECT_ROOT — 向后兼容别名，等同于 DATA_DIR
# ============================================================================

# 计算平台标准的 User App Data 目录
def get_user_data_dir() -> Path:
    if sys.platform == 'win32':
        app_data = os.environ.get('APPDATA')
        if app_data:
            base_dir = Path(app_data)
        else:
            base_dir = Path.home() / 'AppData' / 'Roaming'
    elif sys.platform == 'darwin':
        base_dir = Path.home() / 'Library' / 'Application Support'
    else:
        base_dir = Path.home() / '.config'
    return base_dir / 'JAV SCRAPER'

USER_DATA_DIR = get_user_data_dir()
try:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

if getattr(sys, 'frozen', False):
    # ---- PyInstaller 打包态 ----
    BUNDLE_DIR = Path(sys._MEIPASS)
    # DATA_DIR: 可写的标准用户数据目录
    DATA_DIR = USER_DATA_DIR
else:
    # ---- 开发态 (python3 main.py) ----
    BUNDLE_DIR = Path(__file__).parent
    DATA_DIR = USER_DATA_DIR

# 向后兼容
PROJECT_ROOT = DATA_DIR

# 输出目录配置
OUTPUT_DIR = {
    'root': Path.home() / 'Downloads' / 'JAV SCRAPER',
    'csv': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'csv',
    'json': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'json',
    'images': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'images',
    'magnets': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'magnets',
}

# 提供按需创建输出目录的函数，防止在未运行任务时污染 Downloads 文件夹
def ensure_output_dirs():
    for dir_path in OUTPUT_DIR.values():
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # 打包环境下某些路径可能暂时不可写，不阻塞启动

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
    'max_pages': 100,
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

# Cookie 文件 — 必须始终放置在可读写的 DATA_DIR 下
COOKIE_FILE = str(DATA_DIR / 'cookies.json')

# 如果 DATA_DIR 下还没有 cookies.json，而 BUNDLE_DIR 下存在打包内嵌的 cookies.json，
# 则在初始化时安全地将其复制到 DATA_DIR 下，以保证后续写操作正常。
_cookie_user = DATA_DIR / 'cookies.json'
_cookie_bundle = BUNDLE_DIR / 'cookies.json'
if not _cookie_user.exists() and _cookie_bundle.exists():
    try:
        import shutil
        shutil.copyfile(str(_cookie_bundle), str(_cookie_user))
    except Exception as e:
        print(f"初始化复制 Cookie 文件失败: {e}")

# 自动迁移历史配置文件逻辑
def migrate_legacy_configs():
    # 原有的老配置文件位置 (在运行目录下)
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable)
        exe_dir = exe_path.parent
        if "Contents/MacOS" in str(exe_dir):
            legacy_dir = exe_dir.parent.parent.parent
        else:
            legacy_dir = exe_dir
    else:
        legacy_dir = Path(__file__).parent

    files_to_migrate = ['cookies.json', 'settings_backup.json', 'tasks_backup.json']
    
    for filename in files_to_migrate:
        legacy_file = legacy_dir / filename
        new_file = DATA_DIR / filename
        
        # 如果新旧路径相同，直接跳过
        if legacy_file.resolve() == new_file.resolve():
            continue
            
        # 如果老目录文件存在，且新目录文件不存在，则拷贝到新目录
        if legacy_file.exists() and not new_file.exists():
            try:
                import shutil
                shutil.copyfile(str(legacy_file), str(new_file))
                print(f"成功迁移历史配置: {filename} -> {new_file}")
            except Exception as e:
                print(f"迁移配置 {filename} 失败: {e}")
        
        # 迁移完毕或新旧文件均存在时，安全清理老文件以防污染应用目录
        if legacy_file.exists() and new_file.exists():
            try:
                os.remove(str(legacy_file))
                print(f"已清理历史残留文件: {legacy_file}")
            except Exception as e:
                pass

migrate_legacy_configs()

# 登录配置 - 请填入你的账号信息
LOGIN = {
    'username': '',  # 你的用户名
    'password': '',  # 你的密码
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