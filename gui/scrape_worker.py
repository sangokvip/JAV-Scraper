import os
import shutil
import traceback
import requests
from PySide6.QtCore import QRunnable, QObject, Signal
from lib import AdapterFactory

class WorkerSignals(QObject):
    started = Signal(str)           # filepath
    preview_loaded = Signal(str, dict)  # filepath, video_detail
    finished = Signal(str, str)     # filepath, status ("success" or error message)
    progress = Signal(str, str)     # filepath, current action description
    finished_worker = Signal(object) # worker object itself

class ScrapeWorker(QRunnable):
    def __init__(self, file_path: str, code: str, output_dir: str, platform: str, proxies: dict = None, only_scrape: bool = False, cached_detail: dict = None):
        super().__init__()
        self.file_path = file_path
        self.code = code
        self.output_dir = output_dir
        self.platform = platform
        self.proxies = proxies
        self.only_scrape = only_scrape
        self.cached_detail = cached_detail
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
                    self.signals.progress.emit(self.file_path, "正在从平台刮削数据...")
                    
                    # 清除旧的单例缓存，保证最新的代理/Cookie配置生效
                    AdapterFactory.clear_instance()
                    
                    adapter = AdapterFactory.get_adapter_by_name("javdb", proxies=self.proxies)
                    detail = adapter.get_video_by_code(self.code)

                if not detail:
                    self.signals.finished.emit(self.file_path, f"在平台中找不到番号: {self.code}")
                    return

                # 若不是手动输入的虚拟任务，则将磁力列表置空，不显示磁力
                if not self.file_path.startswith("__virtual__:"):
                    detail["magnets"] = []

                # 发送预览加载信号，供主界面渲染详情卡片
                self.signals.preview_loaded.emit(self.file_path, detail)

                if self.only_scrape:
                    self.signals.finished.emit(self.file_path, "scrape_success")
                    return

                # 2. 文件夹创建与非法字符处理
                actors = detail.get("actors", [])
                actor_name = actors[0].strip() if actors else "未知演员"
                for char in r'\/:*?"<>|':
                    actor_name = actor_name.replace(char, " ")
                actor_name = actor_name.strip() or "未知演员"

                clean_title = detail.get("title", "")
                for char in r'\/:*?"<>|':
                    clean_title = clean_title.replace(char, " ")
                folder_name = f"[{self.code}] {clean_title}"[:60].strip() # 限制最大长度为安全的 60 字符 (防 255 字节文件系统 Invalid argument)
                target_folder = os.path.join(self.output_dir, actor_name, folder_name)
                
                # 安全防御：防范路径穿越 (Path Traversal)，确保目标绝对路径在前缀包含范围内
                abs_target = os.path.abspath(target_folder)
                abs_output = os.path.abspath(self.output_dir)
                if not abs_target.startswith(abs_output):
                    raise PermissionError(f"安全校验失败：目标路径试图跳出根保存目录 ({abs_target})")
                    
                os.makedirs(target_folder, exist_ok=True)

                # 3. 移动并重命名视频文件
                self.signals.progress.emit(self.file_path, "正在移动与重命名影片...")
                ext = os.path.splitext(self.file_path)[1]
                
                # 多CD检测
                cd_suffix = ""
                for cd_keyword in ["-cd1", "-cd2", "-cd3", "_cd1", "_cd2", "_a", "_b"]:
                    if cd_keyword in os.path.basename(self.file_path).lower():
                        cd_suffix = cd_keyword.upper().replace("_", "-")
                        break
                target_video_name = f"{self.code}{cd_suffix}{ext}"
                target_video_path = os.path.join(target_folder, target_video_name)

                # 安全验证：确保视频写入绝对路径前缀被限制在 output_dir 下
                abs_video = os.path.abspath(target_video_path)
                if not abs_video.startswith(abs_output):
                    raise PermissionError(f"安全校验失败：视频写路径试图跳出根保存目录 ({abs_video})")

                # 如果源文件和目标文件不同，则进行移动
                if os.path.exists(self.file_path) and os.path.abspath(self.file_path) != os.path.abspath(target_video_path):
                    try:
                        # 1. 尝试最直接的 os.rename
                        os.rename(self.file_path, target_video_path)
                    except Exception:
                        # 2. 若失败(如跨分区或 exFAT 权限被拒)，采用免 copystat 的纯数据拷贝
                        try:
                            shutil.copyfile(self.file_path, target_video_path)
                            os.remove(self.file_path)
                        except Exception as move_err:
                            raise OSError(move_err.errno if hasattr(move_err, 'errno') else 1, f"移动视频文件失败: {move_err}")

                # 4. 写入元数据 NFO
                self.signals.progress.emit(self.file_path, "正在生成元数据 NFO...")
                nfo_path = os.path.join(target_folder, f"{self.code}.nfo")
                
                # 安全验证：确保 NFO 写入绝对路径前缀被限制在 output_dir 下
                abs_nfo = os.path.abspath(nfo_path)
                if not abs_nfo.startswith(abs_output):
                    raise PermissionError(f"安全校验失败：NFO 写路径试图跳出根保存目录 ({abs_nfo})")
                
                nfo_data = {
                    "code": self.code,
                    "title": detail.get("title", ""),
                    "date": detail.get("date", ""),
                    "studio": detail.get("series", "") or detail.get("maker", "") or detail.get("publisher", "") or detail.get("producer", ""),
                    "tags": detail.get("tags", []),
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

                # 6. 并发下载样品预览图并存放至 extrafanart/
                thumbnails = detail.get("thumbnail_images", [])
                if thumbnails:
                    self.signals.progress.emit(self.file_path, f"正在下载预览图 (0/{len(thumbnails)})...")
                    extrafanart_dir = os.path.join(target_folder, "extrafanart")
                    os.makedirs(extrafanart_dir, exist_ok=True)
                    
                    import concurrent.futures

                    def download_image(args):
                        idx, img_url = args
                        try:
                            # 单张剧照超时时间从 30s 减少到 8s，防止由于单张失效死图阻塞全局
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
                import config
                tb_str = traceback.format_exc()
                try:
                    log_path = os.path.expanduser("~/Desktop/jav_scraper_error.log")
                    with open(log_path, "a", encoding="utf-8") as log_f:
                        log_f.write(f"=== Error for {self.file_path} ===\n{tb_str}\n\n")
                except Exception as log_err:
                    print(f"写入 error.log 失败: {log_err}")
                traceback.print_exc()
                # 对常见的文件系统与硬件级别错误码进行温情化解释
                err_msg = str(e)
                if isinstance(e, OSError):
                    if e.errno == 30: # Read-only file system
                        err_msg = "磁盘已变为只读挂载状态，请重新插拔或检查读写权限"
                    elif e.errno == 22: # Invalid argument
                        err_msg = "文件名过长或路径格式不受当前磁盘文件系统支持"
                    elif e.errno in (1, 13): # Operation not permitted / Permission denied
                        err_msg = "文件正被其他程序(如播放器/下载器)锁定占用或无写入权限"
                self.signals.finished.emit(self.file_path, f"整理异常: {err_msg}")
        finally:
            self.signals.finished_worker.emit(self)
