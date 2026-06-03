import os
import shutil
import traceback
import requests
from PySide6.QtCore import QRunnable, QObject, Signal
from lib import AdapterFactory
from helpers.subtitle_helper import find_matching_subtitles, move_and_rename_subtitles
from helpers.template_helper import format_target_path

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
                 write_subtitle_tag: bool = True, conflict_resolution: str = "keep_both"):
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
        self.signals = WorkerSignals()

    def run(self):
        self.signals.started.emit(self.file_path)
        try:
            try:
                if not self.code:
                    self.signals.finished.emit(self.file_path, "未识别出番号，请双击补充。")
                    return

                if ".." in self.code or "/" in self.code or "\\" in self.code:
                    raise PermissionError(f"安全校验失败：检测到恶意番号或路径穿越符号 ({self.code})")

                if self.cached_detail:
                    detail = self.cached_detail
                    self.signals.progress.emit(self.file_path, "使用已缓存的刮削数据...")
                else:
                    detail = None
                    try:
                        self.signals.progress.emit(self.file_path, "正在从 JAVDB 平台刮削数据...")
                        AdapterFactory.clear_instance()
                        adapter = AdapterFactory.get_adapter_by_name(
                            "javdb", 
                            proxies=self.proxies
                        )
                        detail = adapter.get_video_by_code(self.code)
                    except Exception as scrape_err:
                        print(f"[JAVDB] 刮削过程中发生网络异常: {scrape_err}")

                    # 若 JAVDB 刮削失败或返回空，降级回退至 JAV321 直连
                    if not detail:
                        try:
                            self.signals.progress.emit(self.file_path, "JAVDB 刮削失败，正在降级回退至 JAV321 (直连)...")
                            AdapterFactory.clear_instance()
                            adapter_fallback = AdapterFactory.get_adapter_by_name("jav321", proxies=self.proxies)
                            detail = adapter_fallback.get_video_by_code(self.code)
                            if detail:
                                self.signals.progress.emit(self.file_path, "成功从 JAV321 平台获取到刮削数据。")
                        except Exception as fallback_err:
                            print(f"[JAV321] 降级刮削也失败: {fallback_err}")

                if not detail:
                    self.signals.finished.emit(self.file_path, f"在平台中找不到番号: {self.code}")
                    return

                if not self.file_path.startswith("__virtual__:"):
                    detail["magnets"] = []

                self.signals.preview_loaded.emit(self.file_path, detail)

                if self.only_scrape:
                    self.signals.finished.emit(self.file_path, "scrape_success")
                    return

                # 2. 根据模板计算目标文件夹绝对路径
                self.signals.progress.emit(self.file_path, "正在生成归档路径...")
                target_folder = format_target_path(self.rename_template, self.output_dir, self.code, detail)
                
                # 安全防御
                abs_target = os.path.abspath(target_folder)
                abs_output = os.path.abspath(self.output_dir)
                if not abs_target.startswith(abs_output):
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
                    self.signals.progress.emit(self.file_path, "正在移动与重命名影片及外挂字幕...")
                    
                    for idx, v_path in enumerate(video_files):
                        ext = os.path.splitext(v_path)[1]
                        
                        # 查找外挂字幕
                        subs = find_matching_subtitles(v_path)
                        if subs:
                            has_subtitle_file = True
                            
                        # 智能多 CD 命名规则
                        cd_suffix = ""
                        # 先尝试匹配原文件名中已有的分段标记
                        for cd_keyword in ["-cd1", "-cd2", "-cd3", "_cd1", "_cd2", "_a", "_b"]:
                            if cd_keyword in os.path.basename(v_path).lower():
                                cd_suffix = cd_keyword.upper().replace("_", "-")
                                break
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
                                # 附带副本后缀
                                target_video_name = f"{self.code}{cd_suffix}_副本{ext}"
                                target_video_path = os.path.join(target_folder, target_video_name)
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
                                    shutil.copyfile(v_path, target_video_path)
                                    os.remove(v_path)
                                except Exception as move_err:
                                    raise OSError(move_err.errno if hasattr(move_err, 'errno') else 1, f"移动视频失败: {move_err}")
                        
                        # 同步移动外挂字幕
                        if subs:
                            move_and_rename_subtitles(v_path, target_video_path, subs)

                # 4. 写入元数据 NFO
                self.signals.progress.emit(self.file_path, "正在生成元数据 NFO...")
                nfo_path = os.path.join(target_folder, f"{self.code}.nfo")
                
                abs_nfo = os.path.abspath(nfo_path)
                if not abs_nfo.startswith(abs_output):
                    raise PermissionError(f"安全校验失败：NFO 写路径试图跳出根保存目录 ({abs_nfo})")
                
                # 是否判定为中文字幕
                is_chinese_sub = False
                if self.code.endswith("C") or "中文字幕" in detail.get("tags", []) or has_subtitle_file:
                    is_chinese_sub = True
                    
                tags = list(detail.get("tags", []))
                if is_chinese_sub and self.write_subtitle_tag and "中文字幕" not in tags:
                    tags.append("中文字幕")
                
                nfo_data = {
                    "code": self.code,
                    "title": detail.get("title", ""),
                    "date": detail.get("date", ""),
                    "studio": detail.get("series", "") or detail.get("maker", "") or detail.get("publisher", "") or detail.get("producer", ""),
                    "tags": tags,
                    "actors": detail.get("actors", []),
                    "plot": ""
                }
                from lib.nfo_generator import generate_nfo
                generate_nfo(nfo_data, nfo_path)

                # 5. 下载海报大图 poster.jpg
                self.signals.progress.emit(self.file_path, "正在下载封面大图...")
                cover_url = detail.get("cover_url")
                if cover_url:
                    r = requests.get(cover_url, timeout=10, proxies=self.proxies)
                    if r.status_code == 200:
                        with open(os.path.join(target_folder, "poster.jpg"), "wb") as f:
                            f.write(r.content)

                # 6. 下载样品预览图 (根据偏好设置控制)
                thumbnails = detail.get("thumbnail_images", [])
                if thumbnails and self.download_samples:
                    self.signals.progress.emit(self.file_path, f"正在下载预览图 (0/{len(thumbnails)})...")
                    extrafanart_dir = os.path.join(target_folder, "extrafanart")
                    os.makedirs(extrafanart_dir, exist_ok=True)
                    
                    import concurrent.futures

                    def download_image(args):
                        idx, img_url = args
                        try:
                            r = requests.get(img_url, timeout=8, proxies=self.proxies)
                            if r.status_code == 200:
                                img_path = os.path.join(extrafanart_dir, f"fanart{idx+1}.jpg")
                                with open(img_path, "wb") as f:
                                    f.write(r.content)
                                return True
                        except Exception as img_err:
                            print(f"下载剧照失败 {img_url}: {img_err}")
                        return False

                    completed = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                        tasks = {executor.submit(download_image, (idx, img_url)): idx for idx, img_url in enumerate(thumbnails)}
                        for future in concurrent.futures.as_completed(tasks):
                            completed += 1
                            self.signals.progress.emit(self.file_path, f"正在下载预览图 ({completed}/{len(thumbnails)})...")

                self.signals.finished.emit(self.file_path, "success")

            except Exception as e:
                tb_str = traceback.format_exc()
                try:
                    log_path = os.path.expanduser("~/Desktop/jav_scraper_error.log")
                    with open(log_path, "a", encoding="utf-8") as log_f:
                        log_f.write(f"=== Error for {self.file_path} ===\n{tb_str}\n\n")
                except Exception as log_err:
                    print(f"写入 error.log 失败: {log_err}")
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
