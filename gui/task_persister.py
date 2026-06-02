import os
import json

DEFAULT_BACKUP_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tasks_backup.json")
)

def save_tasks_backup(task_files: dict, filepath: str = DEFAULT_BACKUP_PATH):
    """
    将当前所有的任务信息（排队、刮削、整理状态）序列化写入本地 JSON 中。
    
    Args:
        task_files: 任务字典
        filepath: 备份保存路径
    """
    try:
        # 序列化去除不可序列化的对象（如 QRunnable 实例）
        serializable_tasks = {}
        for fp, info in task_files.items():
            serializable_tasks[fp] = {
                "code": info.get("code", ""),
                "row": info.get("row", 0),
                "status": info.get("status", "等待中"),
                "detail": info.get("detail")
            }
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable_tasks, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存任务备份失败: {e}")

def load_tasks_backup(filepath: str = DEFAULT_BACKUP_PATH) -> dict:
    """
    自本地载入上一期退出/中断时未处理完的任务备份列表并恢复。
    
    Args:
        filepath: 备份保存路径
        
    Returns:
        恢复出的任务字典，不存在时返回空字典 {}
    """
    if not os.path.exists(filepath):
        return {}
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 验证载入结构合理性并清理物理不存在的普通文件
        restored_tasks = {}
        for fp, info in data.items():
            # 虚拟手动番号不受本地物理路径检验限制，本地文件需要进行有效性过滤
            if fp.startswith("__virtual__:") or os.path.exists(fp):
                restored_tasks[fp] = {
                    "code": info.get("code", ""),
                    "row": info.get("row", 0),
                    "status": info.get("status", "等待中"),
                    "detail": info.get("detail")
                }
        return restored_tasks
    except Exception as e:
        print(f"加载任务备份失败: {e}")
        return {}

DEFAULT_SETTINGS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "settings_backup.json")
)

def save_settings_backup(settings: dict, filepath: str = DEFAULT_SETTINGS_PATH):
    """
    保存轻量系统设置（如保存目标路径）至本地 JSON。
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存设置失败: {e}")

def load_settings_backup(filepath: str = DEFAULT_SETTINGS_PATH) -> dict:
    """
    读取本地已存在的系统设置，不存在时返回空字典 {}。
    """
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载设置失败: {e}")
        return {}

