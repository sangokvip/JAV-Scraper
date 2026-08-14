"""
整理操作日志。

每次「整理落盘」成功后记录全部文件移动（视频 + 字幕）与目标目录，
供「撤销整理」按日志精确回滚——不猜测、只回放。
"""
import json
import os
import re
import time

import config

JOURNAL_DIR = config.DATA_DIR / "undo_journal"


def _journal_path(code: str):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', code.upper())
    return JOURNAL_DIR / f"{safe}.json"


def save(code: str, record: dict):
    try:
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        record = dict(record)
        record["saved_at"] = time.time()
        path = _journal_path(code)
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        # 日志写失败只损失撤销能力，不应中断整理主流程
        pass


def load(code: str):
    path = _journal_path(code)
    try:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def delete(code: str):
    try:
        _journal_path(code).unlink(missing_ok=True)
    except Exception:
        pass
