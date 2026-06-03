#!/usr/bin/env python3
"""诊断脚本：打印打包后的 config 路径定位"""
import sys, os

# 模拟 PyInstaller frozen 环境的路径逻辑
print("=== 路径诊断 ===")
print(f"sys.frozen: {getattr(sys, 'frozen', False)}")
print(f"sys.executable: {sys.executable}")
print(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
print(f"os.getcwd(): {os.getcwd()}")
print(f"__file__: {__file__}")

# 导入 config
sys.path.insert(0, os.path.dirname(__file__))
import config
print(f"\nconfig.PROJECT_ROOT: {config.PROJECT_ROOT}")
print(f"config.COOKIE_FILE: {config.COOKIE_FILE}")
print(f"config.OUTPUT_DIR root: {config.OUTPUT_DIR['root']}")

# 检查 task_persister 的路径
from gui.task_persister import DEFAULT_BACKUP_PATH, DEFAULT_SETTINGS_PATH
print(f"\nDEFAULT_BACKUP_PATH: {DEFAULT_BACKUP_PATH}")
print(f"DEFAULT_SETTINGS_PATH: {DEFAULT_SETTINGS_PATH}")

# 检查 settings 内容
from gui.task_persister import load_settings_backup
settings = load_settings_backup()
print(f"\nsettings content: {settings}")
print(f"output_dir from settings: {settings.get('output_dir', '(not set)')}")

# 测试写入能力
test_file = os.path.join(str(config.PROJECT_ROOT), "_write_test.tmp")
try:
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)
    print(f"\n✅ PROJECT_ROOT 可写: {config.PROJECT_ROOT}")
except Exception as e:
    print(f"\n❌ PROJECT_ROOT 不可写: {e}")
