"""
按番号磁盘缓存刮削详情。

同一番号在 TTL 内重复刮削直接命中本地缓存，零网络请求——
既加速批量重跑，也降低出网频率与封禁风险。
"""
import json
import os
import re
import time

import config

CACHE_DIR = config.DATA_DIR / "detail_cache"
TTL_SECONDS = 7 * 86400  # 7 天：元数据基本不变，磁力/评分允许一周内滞后


def _cache_path(platform: str, code: str):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', f"{platform}_{code.upper()}")
    return CACHE_DIR / f"{safe}.json"


def get(platform: str, code: str):
    """命中且未过期返回 detail dict，否则返回 None。"""
    path = _cache_path(platform, code)
    try:
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def put(platform: str, code: str, detail: dict):
    """写入缓存，失败静默（缓存不可用不应影响主流程）。"""
    if not detail:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(platform, code)
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass
