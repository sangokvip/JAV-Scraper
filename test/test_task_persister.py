import os
import json
import tempfile
from gui.task_persister import (
    save_tasks_backup, load_tasks_backup,
    save_settings_backup, load_settings_backup
)

def test_task_persister_save_and_load():
    # 创建临时测试文件存储备份
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        backup_path = tmp.name
        
    # 创建一个真实的临时视频文件，用于通过 os.path.exists 安全验证
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_tmp:
        video_path = video_tmp.name

    try:
        # 1. 模拟任务队列状态
        mock_tasks = {
            video_path: {
                "code": "ABP-123",
                "row": 0,
                "status": "已整理成功",
                "detail": {
                    "code": "ABP-123",
                    "title": "Mock Title 1",
                    "date": "2026-01-01",
                    "magnets": [],
                    "tags": ["Tag A"],
                    "actors": ["Actor A"]
                }
            },
            "__virtual__:SSIS-865": {
                "code": "SSIS-865",
                "row": 1,
                "status": "已刮削(未整理)",
                "detail": {
                    "code": "SSIS-865",
                    "title": "Mock Title 2",
                    "date": "2026-02-02",
                    "magnets": [{"magnet": "magnet:?xt=urn:btih:123", "size_text": "2GB"}],
                    "tags": ["Tag B"],
                    "actors": ["Actor B"]
                }
            }
        }
        
        # 保存备份
        save_tasks_backup(mock_tasks, filepath=backup_path)
        
        # 验证备份内容存在
        assert os.path.exists(backup_path)
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 2
        assert data["__virtual__:SSIS-865"]["code"] == "SSIS-865"
        
        # 从备份载入
        loaded_tasks = load_tasks_backup(filepath=backup_path)
        assert len(loaded_tasks) == 2
        assert loaded_tasks[video_path]["status"] == "已整理成功"
        assert loaded_tasks[video_path]["detail"]["title"] == "Mock Title 1"
        assert len(loaded_tasks["__virtual__:SSIS-865"]["detail"]["magnets"]) == 1
        
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(video_path):
            os.remove(video_path)
            
def test_task_persister_load_missing_file():
    # 模拟载入不存在的文件，应返回空字典而不报错
    loaded_tasks = load_tasks_backup(filepath="/path/to/does_not_exist_backup_123.json")
    assert loaded_tasks == {}

def test_settings_persister_save_and_load():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        settings_path = tmp.name
    try:
        mock_settings = {
            "output_dir": "/Volumes/homes/Download/output"
        }
        save_settings_backup(mock_settings, filepath=settings_path)
        assert os.path.exists(settings_path)
        
        loaded = load_settings_backup(filepath=settings_path)
        assert loaded == mock_settings
        assert loaded["output_dir"] == "/Volumes/homes/Download/output"
    finally:
        if os.path.exists(settings_path):
            os.remove(settings_path)

def test_settings_persister_load_missing_file():
    loaded = load_settings_backup(filepath="/path/to/does_not_exist_settings_123.json")
    assert loaded == {}

