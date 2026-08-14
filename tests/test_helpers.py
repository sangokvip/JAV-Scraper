import json
import os
import time

import pytest

from gui import task_status as TS
from gui.task_persister import save_tasks_backup, load_tasks_backup
from helpers.duplicate_detector import build_organized_code_index
from helpers.template_helper import format_target_path
from lib import detail_cache
from lib.nfo_generator import generate_nfo
from lib.rate_limiter import RateLimiter


# ---------- task_status ----------

def test_status_predicates():
    assert TS.is_running(TS.ORGANIZING)
    assert TS.is_running("正在跨盘复制影片... 45%")  # 旧版备份兼容
    assert TS.is_failed(TS.failed("网络超时"))
    assert TS.is_failed("整理异常: xxx")             # 旧版自由文本兼容
    assert TS.is_success(TS.ORGANIZED)
    assert not TS.is_failed(TS.SCRAPED)
    assert TS.CANCELLED in TS.PENDING_STATES


def test_display_text_prefix_only_in_display_layer():
    assert TS.display_text(TS.ORGANIZED).startswith("✅")
    assert TS.display_text(TS.failed("x")).startswith("❌")
    assert TS.display_text(TS.WAITING) == TS.WAITING


# ---------- task_persister ----------

def test_backup_roundtrip_and_bak_fallback(tmp_path):
    p = str(tmp_path / "tasks.json")
    tasks = {"__virtual__:ABC-1": {"code": "ABC-1", "row": 0, "status": TS.WAITING,
                                   "detail": None, "extra_files": []}}
    save_tasks_backup(tasks, p)
    assert load_tasks_backup(p) == tasks
    save_tasks_backup(tasks, p)          # 产生 .bak
    with open(p, "w") as f:
        f.write("{corrupt")               # 损坏主文件
    assert load_tasks_backup(p) == tasks  # 从 .bak 回退


# ---------- detail_cache ----------

def test_detail_cache_ttl(monkeypatch, tmp_path):
    monkeypatch.setattr(detail_cache, "CACHE_DIR", tmp_path)
    detail_cache.put("javdb", "ABC-123", {"title": "t"})
    assert detail_cache.get("javdb", "ABC-123") == {"title": "t"}
    p = detail_cache._cache_path("javdb", "ABC-123")
    expired = time.time() - detail_cache.TTL_SECONDS - 10
    os.utime(p, (expired, expired))
    assert detail_cache.get("javdb", "ABC-123") is None


# ---------- rate_limiter ----------

def test_rate_limiter_spacing():
    lim = RateLimiter(0.05)
    t0 = time.monotonic()
    for _ in range(3):
        lim.acquire()
    assert time.monotonic() - t0 >= 0.09  # 3 次请求至少跨 2 个间隔


# ---------- duplicate_detector ----------

def test_organized_index_two_level(tmp_path):
    (tmp_path / "[ABC-001] 扁平归档").mkdir()
    actor = tmp_path / "演员A"
    actor.mkdir()
    (actor / "[DEF-002] 二级归档").mkdir()
    (actor / "not_a_code_dir").mkdir()
    (tmp_path / "loose_file.txt").write_text("x")

    index = build_organized_code_index(str(tmp_path))
    assert index["ABC-001"].endswith("[ABC-001] 扁平归档")
    assert index["DEF-002"].endswith("[DEF-002] 二级归档")
    assert len(index) == 2


# ---------- template_helper ----------

def test_format_target_path_basic(tmp_path):
    detail = {"actors": ["七沢みあ"], "title": "标题:含非法/字符", "date": "2023-05-12"}
    path = format_target_path("{actor}/{[code]} {title}", str(tmp_path), "MIDA-583", detail)
    assert path.startswith(str(tmp_path))
    assert "七沢みあ" in path
    assert "[MIDA-583]" in path
    assert ":" not in os.path.basename(path)
    assert ".." not in path


def test_format_target_path_traversal_blocked(tmp_path):
    detail = {"actors": ["../../evil"], "title": "t", "date": ""}
    path = format_target_path("{actor}/{code}", str(tmp_path), "ABC-1", detail)
    assert path.startswith(str(tmp_path))


# ---------- nfo_generator ----------

def test_nfo_fields(tmp_path):
    out = str(tmp_path / "t.nfo")
    generate_nfo({
        "code": "ABC-123", "title": "T", "date": "2026-01-01",
        "studio": "片商S", "series": "系列X",
        "tags": ["a", "b"], "actors": ["n"], "plot": "p",
    }, out)
    content = open(out, encoding="utf-8").read()
    assert "<studio>片商S</studio>" in content
    assert "<name>系列X</name>" in content        # series 进 <set>，不进 studio
    assert "系列X</studio>" not in content
    assert "<plot>p</plot>" in content
    assert content.count("<genre>") == 2
    assert "fanart.jpg" in content
