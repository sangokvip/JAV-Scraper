import json
import os
import re
import shutil
import threading
import traceback
import requests
from PySide6.QtCore import QRunnable, QObject, Signal
from lib import AdapterFactory
from lib import detail_cache
from helpers.subtitle_helper import find_matching_subtitles, move_and_rename_subtitles
from helpers.template_helper import format_target_path
from lib.logger import get_logger

log = get_logger(__name__)

# 线程本地适配器缓存：QThreadPool 的每个工作线程复用自己的实例
# （连接与 TLS 会话得以保持），线程之间互不共享（并发安全）。
# 切勿改回 AdapterFactory 的类级单例——多 worker 并发时会互相清除实例。
_thread_local = threading.local()


def _get_thread_adapter(platform_name: str, proxies: dict = None):
    key = f"{platform_name}:{json.dumps(proxies, sort_keys=True, default=str)}"
    cache = getattr(_thread_local, 'adapters', None)
    if cache is None:
        cache = _thread_local.adapters = {}
    if key not in cache:
        cache[key] = AdapterFactory.create_adapter(platform_name, proxies=proxies)
    return cache[key]

class WorkerSignals(QObject):
    started = Signal(str)           # filepath
    preview_loaded = Signal(str, dict)  # filepath, video_detail
    finished = Signal(str, str)     # filepath, status ("success" or error message)
    progress = Signal(str, str)     # filepath, current action description
    finished_worker = Signal(object) # worker object itself

class ScrapeWorker(QRunnable):
    def __init__(self, file_path: str, code: str, output_dir: str, platform: str, proxies: dict = None, 
                 only_scrape: bool = False, cached_detail: dict = None, extra_files: list = None,
                 rename_template: str = "{actor}/{[code]} {title}", download_samples: bool = True,
                 write_subtitle_tag: bool = True, conflict_resolution: str = "keep_both",
                 force_refresh: bool = False):
        super().__init__()
        self.file_path = file_path
        self.code = code
        self.output_dir = output_dir
        self.platform = platform
        self.proxies = proxies
        self.only_scrape = only_scrape
        self.cached_detail = cached_detail
        self.extra_files = extra_files if extra_files is not None else []
        self.rename_template = rename_template
        self.download_samples = download_samples
        self.write_subtitle_tag = write_subtitle_tag
        self.conflict_resolution = conflict_resolution
        self.force_refresh = force_refresh
        self.signals = WorkerSignals()
        self.is_cancelled = False

    def _copy_file_cancellable(self, src: str, dst: str, chunk_size: int = 16 * 1024 * 1024):
        """
        分块复制，块间检查取消标记。
        被取消时删除写了一半的目标文件后返回（不删源文件）。
        """
        total = os.path.getsize(src)
        copied = 0
        try:
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                while True:
                    if self.is_cancelled:
                        break
                    chunk = fsrc.read(chunk_size)
                    if not chunk:
                        break
                    fdst.write(chunk)
                    copied += len(chunk)
                    if total > 0:
                        self.signals.progress.emit(
                            self.file_path, f"正在跨盘复制影片... {copied * 100 // total}%")
        except Exception:
            try:
                os.remove(dst)
            except OSError:
                pass
            raise
        if self.is_cancelled:
            try:
                os.remove(dst)
            except OSError:
                pass

    def run(self):
        self.signals.started.emit(self.file_path)
        try:
            try:
                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return

                if not self.code:
                    self.signals.finished.emit(self.file_path, "未识别出番号，请双击补充。")
                    return

                if ".." in self.code or "/" in self.code or "\\" in self.code:
                    raise PermissionError(f"安全校验失败：检测到恶意番号或路径穿越符号 ({self.code})")

                last_error = None
                if self.cached_detail:
                    # 浅拷贝：cached_detail 与主线程共享同一对象，
                    # 工作线程直接改（如清空 magnets）会与预览渲染竞争
                    detail = dict(self.cached_detail)
                    self.signals.progress.emit(self.file_path, "使用已缓存的刮削数据...")
                else:
                    detail = None

                    # 磁盘缓存：TTL 内同番号重复刮削零网络请求。
                    # 用户明确要求重新刮削时（force_refresh）跳过缓存
                    if not self.force_refresh:
                        detail = detail_cache.get("javdb", self.code)
                        if detail:
                            self.signals.progress.emit(self.file_path, "命中本地刮削缓存...")

                    if not detail:
                        try:
                            if self.is_cancelled:
                                self.signals.finished.emit(self.file_path, "cancelled")
                                return
                            self.signals.progress.emit(self.file_path, "正在从 JAVDB 平台刮削数据...")
                            adapter = _get_thread_adapter("javdb", self.proxies)
                            detail = adapter.get_video_by_code(self.code)
                            if detail:
                                detail_cache.put("javdb", self.code, detail)
                        except Exception as scrape_err:
                            last_error = scrape_err
                            log.error(f"[JAVDB] 刮削过程中发生网络异常: {scrape_err}")

                    # 若 JAVDB 刮削失败或返回空，降级回退至 JAV321 直连
                    if not detail:
                        try:
                            if self.is_cancelled:
                                self.signals.finished.emit(self.file_path, "cancelled")
                                return
                            self.signals.progress.emit(self.file_path, "JAVDB 刮削失败，正在降级回退至 JAV321 (直连)...")
                            adapter_fallback = _get_thread_adapter("jav321", self.proxies)
                            detail = adapter_fallback.get_video_by_code(self.code)
                            if detail:
                                detail_cache.put("javdb", self.code, detail)
                                self.signals.progress.emit(self.file_path, "成功从 JAV321 平台获取到刮削数据。")
                        except Exception as fallback_err:
                            last_error = fallback_err
                            log.error(f"[JAV321] 降级刮削也失败: {fallback_err}")

                if not detail:
                    # 区分"确实查不到"与"网络/代理异常"，否则用户无从排查
                    if last_error is not None:
                        self.signals.finished.emit(self.file_path, f"刮削失败 ({last_error})")
                    else:
                        self.signals.finished.emit(self.file_path, f"在平台中找不到番号: {self.code}")
                    return

                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return

                if not self.file_path.startswith("__virtual__:"):
                    detail["magnets"] = []

                self.signals.preview_loaded.emit(self.file_path, detail)

                if self.only_scrape:
                    self.signals.finished.emit(self.file_path, "scrape_success")
                    return

                # 2. 根据模板计算目标文件夹绝对路径
                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return
                self.signals.progress.emit(self.file_path, "正在生成归档路径...")
                target_folder = format_target_path(self.rename_template, self.output_dir, self.code, detail)
                
                # 安全防御（commonpath 而非 startswith，避免 /out-backup 被误判在 /out 内）
                abs_target = os.path.abspath(target_folder)
                abs_output = os.path.abspath(self.output_dir)
                if os.path.commonpath([abs_target, abs_output]) != abs_output:
                    raise PermissionError(f"安全校验失败：目标路径试图跳出根保存目录 ({abs_target})")
                    
                os.makedirs(target_folder, exist_ok=True)

                # 3. 处理字幕和重命名整理
                has_subtitle_file = False
                video_files = []
                if not self.file_path.startswith("__virtual__:"):
                    video_files = [self.file_path] + self.extra_files
                    # 过滤掉物理不存在的文件
                    video_files = [f for f in video_files if os.path.exists(f)]
                    video_files.sort() # 保证 -cd1, -cd2 顺序稳定

                if video_files:
                    if self.is_cancelled:
                        self.signals.finished.emit(self.file_path, "cancelled")
                        return
                    self.signals.progress.emit(self.file_path, "正在移动与重命名影片及外挂字幕...")
                    
                    for idx, v_path in enumerate(video_files):
                        if self.is_cancelled:
                            self.signals.finished.emit(self.file_path, "cancelled")
                            return
                        ext = os.path.splitext(v_path)[1]
                        
                        # 查找外挂字幕
                        subs = find_matching_subtitles(v_path)
                        if subs:
                            has_subtitle_file = True
                            
                        # 智能多 CD 命名规则
                        cd_suffix = ""
                        # 只匹配文件名"末尾"的分段标记，避免 file_backup.mp4 里的 _b 误判
                        base_no_ext = os.path.splitext(os.path.basename(v_path))[0].lower()
                        cd_match = re.search(r'[-_](cd\d+|[ab])$', base_no_ext)
                        if cd_match:
                            cd_suffix = f"-{cd_match.group(1).upper()}"
                        # 如果没有分段标记但确实有多个视频，按索引分段
                        if not cd_suffix and len(video_files) > 1:
                            cd_suffix = f"-CD{idx+1}"
                            
                        target_video_name = f"{self.code}{cd_suffix}{ext}"
                        target_video_path = os.path.join(target_folder, target_video_name)
                        
                        # 冲突检验与解决
                        if os.path.exists(target_video_path):
                            if self.conflict_resolution == "skip":
                                continue
                            elif self.conflict_resolution == "only_meta":
                                pass # 不移动视频，继续往下做元数据写入
                            elif self.conflict_resolution == "keep_both":
                                # 附带副本后缀，探测到不存在的名字为止，避免覆盖旧副本
                                copy_idx = 1
                                while True:
                                    copy_tag = "_副本" if copy_idx == 1 else f"_副本{copy_idx}"
                                    target_video_name = f"{self.code}{cd_suffix}{copy_tag}{ext}"
                                    target_video_path = os.path.join(target_folder, target_video_name)
                                    if not os.path.exists(target_video_path):
                                        break
                                    copy_idx += 1
                            elif self.conflict_resolution == "overwrite":
                                try:
                                    os.remove(target_video_path)
                                except Exception:
                                    pass

                        # 执行物理移动或拷贝
                        if self.conflict_resolution != "only_meta" and os.path.abspath(v_path) != os.path.abspath(target_video_path):
                            try:
                                os.rename(v_path, target_video_path)
                            except Exception:
                                try:
                                    # 跨盘降级为分块复制：几十 GB 的文件期间可响应取消
                                    self._copy_file_cancellable(v_path, target_video_path)
                                    if self.is_cancelled:
                                        self.signals.finished.emit(self.file_path, "cancelled")
                                        return
                                    os.remove(v_path)
                                except Exception as move_err:
                                    raise OSError(move_err.errno if hasattr(move_err, 'errno') else 1, f"移动视频失败: {move_err}")
                        
                        # 同步移动外挂字幕
                        if subs:
                            move_and_rename_subtitles(v_path, target_video_path, subs)

                # 4. 写入元数据 NFO
                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return
                self.signals.progress.emit(self.file_path, "正在生成元数据 NFO...")
                nfo_path = os.path.join(target_folder, f"{self.code}.nfo")
                
                abs_nfo = os.path.abspath(nfo_path)
                if os.path.commonpath([abs_nfo, abs_output]) != abs_output:
                    raise PermissionError(f"安全校验失败：NFO 写路径试图跳出根保存目录 ({abs_nfo})")
                
                # 是否判定为中文字幕。
                # 注意不能用 self.code.endswith("C")：code_extractor 在提取时
                # 已剥掉 -C/-CH 后缀，只能回看原始文件名。
                orig_name = os.path.basename(self.file_path)
                has_c_suffix = bool(
                    re.search(r'(?i)[-_](ch|c)\b', orig_name)
                    or re.search(r'(?<=\d)[cC]\b', orig_name)
                    or "中文" in orig_name or "字幕" in orig_name
                )
                is_chinese_sub = False
                if has_c_suffix or "中文字幕" in detail.get("tags", []) or has_subtitle_file:
                    is_chinese_sub = True
                    
                tags = list(detail.get("tags", []))
                if is_chinese_sub and self.write_subtitle_tag and "中文字幕" not in tags:
                    tags.append("中文字幕")
                
                # studio 只放片商（series 是合集概念，写 <set>，混进 studio 会
                # 污染媒体库的片商筛选）
                # javdb 评分是 5 分制文本（如 "4.48分, 由652人評價"），换算 10 分制
                rating_10 = ""
                rating_match = re.search(r'(\d+(?:\.\d+)?)', str(detail.get("rating", "")))
                if rating_match:
                    rating_10 = f"{float(rating_match.group(1)) * 2:.1f}"

                nfo_data = {
                    "code": self.code,
                    "title": detail.get("title", ""),
                    "date": detail.get("date", ""),
                    "studio": detail.get("maker", "") or detail.get("publisher", "") or detail.get("producer", ""),
                    "series": detail.get("series", ""),
                    "tags": tags,
                    "actors": detail.get("actors", []),
                    "plot": detail.get("plot", ""),
                    "rating": rating_10,
                    "trailer": detail.get("preview_video", ""),
                    "javdb_id": detail.get("video_id", ""),
                }
                from lib.nfo_generator import generate_nfo
                generate_nfo(nfo_data, nfo_path)

                # 5. 下载海报大图 poster.jpg
                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return
                self.signals.progress.emit(self.file_path, "正在下载封面大图...")
                cover_url = detail.get("cover_url")
                if cover_url:
                    r = requests.get(cover_url, timeout=10, proxies=self.proxies)
                    if r.status_code == 200:
                        if self.is_cancelled:
                            self.signals.finished.emit(self.file_path, "cancelled")
                            return
                        with open(os.path.join(target_folder, "poster.jpg"), "wb") as f:
                            f.write(r.content)
                        # NFO 引用了 fanart.jpg，必须真实落盘一份
                        with open(os.path.join(target_folder, "fanart.jpg"), "wb") as f:
                            f.write(r.content)

                # 6. 下载样品预览图 (根据偏好设置控制)
                thumbnails = detail.get("thumbnail_images", [])
                if thumbnails and self.download_samples:
                    if self.is_cancelled:
                        self.signals.finished.emit(self.file_path, "cancelled")
                        return
                    self.signals.progress.emit(self.file_path, f"正在下载预览图 (0/{len(thumbnails)})...")
                    extrafanart_dir = os.path.join(target_folder, "extrafanart")
                    os.makedirs(extrafanart_dir, exist_ok=True)
                    
                    import concurrent.futures

                    def download_image(args):
                        idx, img_url = args
                        if self.is_cancelled:
                            return False
                        try:
                            r = requests.get(img_url, timeout=8, proxies=self.proxies)
                            if r.status_code == 200:
                                if self.is_cancelled:
                                    return False
                                img_path = os.path.join(extrafanart_dir, f"fanart{idx+1}.jpg")
                                with open(img_path, "wb") as f:
                                    f.write(r.content)
                                return True
                        except Exception as img_err:
                            log.error(f"下载剧照失败 {img_url}: {img_err}")
                        return False

                    completed = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                        tasks = {executor.submit(download_image, (idx, img_url)): idx for idx, img_url in enumerate(thumbnails)}
                        for future in concurrent.futures.as_completed(tasks):
                            if self.is_cancelled:
                                break
                            completed += 1
                            self.signals.progress.emit(self.file_path, f"正在下载预览图 ({completed}/{len(thumbnails)})...")

                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return

                self.signals.finished.emit(self.file_path, "success")

            except Exception as e:
                if self.is_cancelled:
                    self.signals.finished.emit(self.file_path, "cancelled")
                    return
                tb_str = traceback.format_exc()
                try:
                    import config
                    log_path = str(config.DATA_DIR / "jav_scraper_error.log")
                    with open(log_path, "a", encoding="utf-8") as log_f:
                        log_f.write(f"=== Error for {self.file_path} ===\n{tb_str}\n\n")
                except Exception as log_err:
                    log.error(f"写入 error.log 失败: {log_err}")
                traceback.print_exc()
                
                err_msg = str(e)
                if isinstance(e, OSError):
                    if e.errno == 30:
                        err_msg = "磁盘已变为只读挂载状态，请重新插拔或检查读写权限"
                    elif e.errno == 22:
                        err_msg = "文件名过长或路径格式不受当前磁盘文件系统支持"
                    elif e.errno in (1, 13):
                        err_msg = "文件正被其他程序(如播放器/下载器)锁定占用或无写入权限"
                self.signals.finished.emit(self.file_path, f"整理异常: {err_msg}")
        finally:
            self.signals.finished_worker.emit(self)
