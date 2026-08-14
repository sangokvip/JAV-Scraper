import os
import json

from config import PROJECT_ROOT
from gui import task_status
from lib.logger import get_logger

log = get_logger(__name__)

DEFAULT_BACKUP_PATH = os.path.abspath(
    os.path.join(PROJECT_ROOT, "tasks_backup.json")
)


def _atomic_dump(obj, filepath: str):
    """
    原子写 JSON：先写 .tmp 再 os.replace，主文件永远不会处于半写状态；
    替换前把上一份完整文件轮转成 .bak 供损坏时回退。
    """
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=4)
        f.flush()
        os.fsync(f.fileno())
    if os.path.exists(filepath):
        os.replace(filepath, filepath + ".bak")
    os.replace(tmp_path, filepath)


def _load_json_with_fallback(filepath: str):
    """
    读主文件，损坏/缺失时回退 .bak。两者都不可用返回 None。
    """
    for candidate in (filepath, filepath + ".bak"):
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if candidate.endswith(".bak"):
                log.info(f"主备份文件损坏，已从 {os.path.basename(candidate)} 回退恢复")
            return data
        except Exception as e:
            log.error(f"加载 {os.path.basename(candidate)} 失败: {e}")
    return None

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
                "status": info.get("status", task_status.WAITING),
                "detail": info.get("detail"),
                "extra_files": info.get("extra_files", [])
            }
            
        _atomic_dump(serializable_tasks, filepath)
    except Exception as e:
        log.error(f"保存任务备份失败: {e}")

def load_tasks_backup(filepath: str = DEFAULT_BACKUP_PATH) -> dict:
    """
    自本地载入上一期退出/中断时未处理完的任务备份列表并恢复。
    
    Args:
        filepath: 备份保存路径
        
    Returns:
        恢复出的任务字典，不存在时返回空字典 {}
    """
    data = _load_json_with_fallback(filepath)
    if data is None:
        return {}

    try:
        # 验证载入结构合理性并清理物理不存在的普通文件
        restored_tasks = {}
        for fp, info in data.items():
            # 虚拟手动番号不受本地物理路径检验限制，本地文件需要进行有效性过滤
            if fp.startswith("__virtual__:") or os.path.exists(fp):
                restored_tasks[fp] = {
                    "code": info.get("code", ""),
                    "row": info.get("row", 0),
                    "status": info.get("status", task_status.WAITING),
                    "detail": info.get("detail"),
                    "extra_files": info.get("extra_files", [])
                }
        return restored_tasks
    except Exception as e:
        log.error(f"加载任务备份失败: {e}")
        return {}

DEFAULT_SETTINGS_PATH = os.path.abspath(
    os.path.join(PROJECT_ROOT, "settings_backup.json")
)

def save_settings_backup(settings: dict, filepath: str = DEFAULT_SETTINGS_PATH):
    """
    保存轻量系统设置（如保存目标路径）至本地 JSON。
    """
    try:
        _atomic_dump(settings, filepath)
    except Exception as e:
        log.error(f"保存设置失败: {e}")

def load_settings_backup(filepath: str = DEFAULT_SETTINGS_PATH) -> dict:
    """
    读取本地已存在的系统设置，不存在时返回空字典 {}。
    """
    data = _load_json_with_fallback(filepath)
    return data if isinstance(data, dict) else {}

