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

class ScrapeWorker(QRunnable):
    def __init__(self, file_path: str, code: str, output_dir: str, platform: str, proxies: dict = None):
        super().__init__()
        self.file_path = file_path
        self.code = code
        self.output_dir = output_dir
        self.platform = platform
        self.proxies = proxies
        self.signals = WorkerSignals()

    def run(self):
        self.signals.started.emit(self.file_path)
        try:
            if not self.code:
                self.signals.finished.emit(self.file_path, "未识别出番号，请双击补充。")
                return

            self.signals.progress.emit(self.file_path, "正在初始化刮削器...")
            
            # 清除旧的单例缓存，保证最新的代理/Cookie配置生效
            AdapterFactory.clear_instance()
            
            if self.platform == "javdb":
                adapter = AdapterFactory.get_adapter_by_name("javdb", proxies=self.proxies)
                detail = adapter.get_video_by_code(self.code)
            else:
                proxy_str = self.proxies.get("http") if self.proxies else None
                adapter = AdapterFactory.get_adapter_by_name("javbus", proxy=proxy_str)
                # JavBus 使用 get_video_detail (用番号直接作为ID)
                detail = adapter.get_video_detail(self.code)

            if not detail:
                self.signals.finished.emit(self.file_path, f"在平台中找不到番号: {self.code}")
                return

            # 发送预览加载信号，供主界面渲染详情卡片
            self.signals.preview_loaded.emit(self.file_path, detail)

            # 2. 文件夹创建与非法字符处理
            clean_title = detail.get("title", "")
            for char in r'\/:*?"<>|':
                clean_title = clean_title.replace(char, " ")
            folder_name = f"[{self.code}] {clean_title}"[:120].strip() # 限制最大长度
            target_folder = os.path.join(self.output_dir, folder_name)
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

            # 如果源文件和目标文件不同，则进行移动
            if os.path.exists(self.file_path) and os.path.abspath(self.file_path) != os.path.abspath(target_video_path):
                shutil.move(self.file_path, target_video_path)

            # 4. 写入元数据 NFO
            self.signals.progress.emit(self.file_path, "正在生成元数据 NFO...")
            nfo_path = os.path.join(target_folder, f"{self.code}.nfo")
            
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
                r = requests.get(cover_url, timeout=30, proxies=self.proxies)
                if r.status_code == 200:
                    with open(os.path.join(target_folder, "poster.jpg"), "wb") as f:
                        f.write(r.content)

            # 6. 下载样品预览图并存放至 extrafanart/
            thumbnails = detail.get("thumbnail_images", [])
            if thumbnails:
                self.signals.progress.emit(self.file_path, f"正在下载预览图 (0/{len(thumbnails)})...")
                extrafanart_dir = os.path.join(target_folder, "extrafanart")
                os.makedirs(extrafanart_dir, exist_ok=True)
                for idx, img_url in enumerate(thumbnails):
                    try:
                        r = requests.get(img_url, timeout=30, proxies=self.proxies)
                        if r.status_code == 200:
                            img_path = os.path.join(extrafanart_dir, f"fanart{idx+1}.jpg")
                            with open(img_path, "wb") as f:
                                f.write(r.content)
                    except Exception as img_err:
                        print(f"下载剧照失败 {img_url}: {img_err}")
                    self.signals.progress.emit(self.file_path, f"正在下载预览图 ({idx+1}/{len(thumbnails)})...")

            self.signals.finished.emit(self.file_path, "success")

        except Exception as e:
            traceback.print_exc()
            self.signals.finished.emit(self.file_path, f"刮削异常: {str(e)}")
