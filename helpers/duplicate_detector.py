import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
from lib.logger import get_logger

log = get_logger(__name__)

# 归档文件夹命名模式："[番号] 标题"，提取方括号内的番号
_CODE_PREFIX_RE = re.compile(r"^\[([^\]]+)\]")


def build_organized_code_index(
    output_dir: str,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    max_workers: int = 16,
) -> dict:
    """
    单次遍历目标归档目录，返回 {番号大写: 归档文件夹路径} 索引。
    支持两级结构（演员/番号 或 扁平番号），供批量防重校验一次查完。

    网络盘（SMB/NFS）上每次 listdir/stat 都是一趟往返：
    用 scandir 免掉逐条目 stat，第二层用线程池并发扫，
    cancel_check 返回 True 时尽快放弃，progress(done, total) 报告二层扫描进度。
    """
    index = {}
    if not output_dir or not os.path.isdir(output_dir):
        return index

    cancelled = cancel_check or (lambda: False)
    actor_dirs = []
    try:
        with os.scandir(output_dir) as it:
            for entry in it:
                if cancelled():
                    return index
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue
                m = _CODE_PREFIX_RE.match(entry.name)
                if m:
                    # 扁平结构：根目录下直接是番号文件夹
                    index.setdefault(m.group(1).upper(), entry.path)
                else:
                    actor_dirs.append(entry.path)
    except OSError as e:
        log.error(f"检索重复归档文件夹异常: {e}")
        return index

    def scan_actor_dir(path):
        found = []
        try:
            with os.scandir(path) as it2:
                for entry in it2:
                    if cancelled():
                        break
                    try:
                        if not entry.is_dir():
                            continue
                    except OSError:
                        continue
                    m2 = _CODE_PREFIX_RE.match(entry.name)
                    if m2:
                        found.append((m2.group(1).upper(), entry.path))
        except OSError:
            pass
        return found

    total = len(actor_dirs)
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scan_actor_dir, p) for p in actor_dirs]
        for future in as_completed(futures):
            if cancelled():
                for f in futures:
                    f.cancel()
                break
            done += 1
            if progress:
                progress(done, total)
            for code, path in future.result():
                index.setdefault(code, path)
    return index
