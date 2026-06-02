import os
import json
import requests
from PySide6.QtCore import QThreadPool, Qt, Signal, QRunnable, QObject
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog, QDialog, QVBoxLayout, QLabel, QTextEdit
from PySide6.QtGui import QPixmap
from gui.main_window import MainWindow
from gui.scrape_worker import ScrapeWorker
from lib.code_extractor import extract_code

class PhotoDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("剧照放大预览")
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel()
        # 放大为最大 800x600
        lbl.setPixmap(pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(lbl)
        self.setLayout(layout)

class ClickableLabel(QLabel):
    clicked = Signal(QPixmap)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap_data = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.pixmap_data:
                self.clicked.emit(self.pixmap_data)

class ImageLoadSignals(QObject):
    loaded = Signal(str, str, bytes)  # filepath, url, content

class ImageLoadWorker(QRunnable):
    def __init__(self, filepath, url, proxies=None):
        super().__init__()
        self.filepath = filepath
        self.url = url
        self.proxies = proxies
        self.signals = ImageLoadSignals()

    def run(self):
        try:
            r = requests.get(self.url, timeout=10, proxies=self.proxies)
            if r.status_code == 200:
                self.signals.loaded.emit(self.filepath, self.url, r.content)
        except Exception as e:
            pass

class Controller:
    def __init__(self, view: MainWindow):
        self.view = view
        self.thread_pool = QThreadPool.globalInstance()
        # 限制并发为 2，防止被平台封锁 IP
        self.thread_pool.setMaxThreadCount(2)
        
        # 存储所有正在排队或执行的任务文件：{file_path: {"code": str, "row": int, "detail": dict, "status": str}}
        self.task_files = {}
        self.current_preview_filepath = None

        # 默认保存路径为项目根目录下的 output 文件夹
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
        self.view.path_input.setText(default_out)

        # 信号槽绑定
        self.view.files_dropped.connect(self.handle_files_dropped)
        self.view.btn_browse.clicked.connect(self.browse_output_dir)
        self.view.btn_clear.clicked.connect(self.clear_all_tasks)
        self.view.btn_import_files.clicked.connect(lambda: self.import_files_manually())
        self.view.btn_import_dir.clicked.connect(lambda: self.import_dir_manually())
        self.view.btn_add_code.clicked.connect(lambda: self.add_code_manually())
        self.view.btn_start.clicked.connect(self.start_scraping)
        self.view.btn_organize.clicked.connect(self.start_organizing)
        self.view.btn_test_proxy.clicked.connect(self.test_proxy_connection)
        self.view.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.view.table.itemChanged.connect(self.handle_cell_changed)
        self.view.btn_save_cookie.clicked.connect(self.save_cookie_config)

        # 自动加载已有的 Cookie 进行显示
        self.load_cookie_config()

    def handle_files_dropped(self, paths: list):
        valid_extensions = ('.mp4', '.mkv', '.avi', '.wmv', '.mov', '.flv', '.rmvb')
        all_files = []
        
        for path in paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith(valid_extensions):
                            all_files.append(os.path.join(root, file))
            elif os.path.isfile(path) and path.lower().endswith(valid_extensions):
                all_files.append(path)

        for file_path in all_files:
            if file_path in self.task_files:
                continue  # 避免重复添加

            # 提取番号
            code = extract_code(os.path.basename(file_path)) or ""
            row = self.view.table.rowCount()
            self.view.table.insertRow(row)

            # ID 列
            id_item = QTableWidgetItem(f"{row + 1:02d}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 0, id_item)

            # 原文件名
            name_item = QTableWidgetItem(os.path.basename(file_path))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 1, name_item)

            # 番号 (可编辑)
            code_item = QTableWidgetItem(code)
            self.view.table.setItem(row, 2, code_item)

            # 当前状态
            status_text = "排队中" if code else "番号待补充"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)

            self.task_files[file_path] = {
                "code": code,
                "row": row,
                "detail": None,
                "status": status_text
            }

    def import_files_manually(self):
        video_filters = "视频文件 (*.mp4 *.mkv *.avi *.wmv *.mov *.flv *.rmvb)"
        files, _ = QFileDialog.getOpenFileNames(self.view, "选择视频文件", "", video_filters)
        if files:
            self.handle_files_dropped(files)

    def import_dir_manually(self):
        dir_path = QFileDialog.getExistingDirectory(self.view, "选择视频文件夹")
        if dir_path:
            self.handle_files_dropped([dir_path])

    def add_code_manually(self):
        from PySide6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(self.view, "手动添加番号", "请输入要刮削的视频番号 (例如 IPX-123):")
        if ok and code.strip():
            code = code.strip().upper()
            virtual_path = f"__virtual__:{code}"
            
            if virtual_path in self.task_files:
                QMessageBox.warning(self.view, "提示", f"番号 {code} 已经存在于任务列表中")
                return
                
            row = self.view.table.rowCount()
            self.view.table.insertRow(row)
            
            # ID 列
            id_item = QTableWidgetItem(f"{row + 1:02d}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 0, id_item)
            
            # 原文件名
            name_item = QTableWidgetItem("[无本地视频: 仅刮削元数据]")
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 1, name_item)
            
            # 番号 (可编辑)
            code_item = QTableWidgetItem(code)
            self.view.table.setItem(row, 2, code_item)
            
            # 当前状态
            status_item = QTableWidgetItem("排队中")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)
            
            self.task_files[virtual_path] = {
                "code": code,
                "row": row,
                "detail": None,
                "status": "排队中"
            }

    def handle_cell_changed(self, item):
        # 当用户在表格中双击编辑修改番号时触发
        if item.column() == 2:
            row = item.row()
            for fp, info in self.task_files.items():
                if info["row"] == row:
                    new_code = item.text().strip()
                    info["code"] = new_code
                    status_item = self.view.table.item(row, 3)
                    if status_item:
                        status_text = "排队中" if new_code else "番号待补充"
                        status_item.setText(status_text)
                        info["status"] = status_text
                    break

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self.view, "选择保存目标文件夹")
        if dir_path:
            self.view.path_input.setText(os.path.abspath(dir_path))

    def clear_all_tasks(self):
        self.view.table.setRowCount(0)
        self.task_files.clear()
        self.reset_preview_panel()

    def reset_preview_panel(self):
        self.view.lbl_cover.setText("选择影片以预览海报")
        self.view.lbl_cover.setPixmap(QPixmap())
        self.view.lbl_info_title.setText("影片番号与标题")
        self.view.lbl_info_details.setText("制片商: -\n发行日期: -\n演员: -")
        self.view.table_magnet.setRowCount(0)
        
        # 清空剧照 samples_layout
        if hasattr(self.view, "samples_layout"):
            while self.view.samples_layout.count():
                item = self.view.samples_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def test_proxy_connection(self):
        proxy = self.view.proxy_input.text().strip()
        self.view.lbl_proxy_status.setText("正在测试连接...")
        self.view.lbl_proxy_status.setStyleSheet("color: #E5C158;")
        
        proxies = {"http": proxy, "https": proxy} if proxy else None
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # 1. 优先尝试访问 google.com 验证代理隧道本身的连通性
        try:
            r = requests.get("https://www.google.com", timeout=8, proxies=proxies, headers=headers)
            if r.status_code == 200:
                self.view.lbl_proxy_status.setText("连接正常 (OK)")
                self.view.lbl_proxy_status.setStyleSheet("color: #34C759;")
                return
        except:
            pass

        # 2. 如果 google 失败或不可达，尝试访问 javdb 并包容 403 (CF 拦截代表物理通畅)
        try:
            r = requests.get("https://javdb.com", timeout=8, proxies=proxies, headers=headers)
            if r.status_code in [200, 301, 302, 403]:
                # JAVDB 常有 Cloudflare 盾，返回 403 仍代表代理打通并能抵达目标网站
                self.view.lbl_proxy_status.setText("连接正常 (OK)")
                self.view.lbl_proxy_status.setStyleSheet("color: #34C759;")
            else:
                self.view.lbl_proxy_status.setText(f"连接失败: 状态码 {r.status_code}")
                self.view.lbl_proxy_status.setStyleSheet("color: #FF453A;")
        except Exception as e:
            self.view.lbl_proxy_status.setText("连接超时/不可用")
            self.view.lbl_proxy_status.setStyleSheet("color: #FF453A;")

    def load_cookie_config(self):
        import config
        import json
        cookie_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", config.COOKIE_FILE))
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_data.items()])
                    self.view.cookie_input.setText(cookie_str)
            except:
                pass

    def save_cookie_config(self):
        import config
        cookie_str = self.view.cookie_input.toPlainText().strip()
        if not cookie_str:
            QMessageBox.information(self.view, "提示", "Cookie 为空")
            return
            
        # 解析 Cookie
        cookies_dict = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies_dict[k.strip()] = v.strip()

        cookie_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", config.COOKIE_FILE))
        try:
            import json
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, indent=2)
            QMessageBox.information(self.view, "成功", "Cookie 已成功保存至本地 cookies.json")
        except Exception as e:
            QMessageBox.critical(self.view, "错误", f"Cookie 保存失败: {e}")

    def start_scraping(self):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return

        proxies = None
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb" if self.view.radio_javdb.isChecked() else "javbus"

        active_tasks = 0
        for file_path, info in self.task_files.items():
            code = info["code"]
            if not code or info["status"] in ["正在刮削...", "已刮削(未整理)", "整理中...", "已整理成功"]:
                continue

            active_tasks += 1
            info["status"] = "正在刮削..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("正在刮削..."))

            # 仅执行刮削预览
            worker = ScrapeWorker(file_path, code, output_dir, platform, proxies, only_scrape=True)
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)

            self.thread_pool.start(worker)

        if active_tasks == 0:
            QMessageBox.information(self.view, "提示", "列表中没有需要刮削的影片")

    def start_organizing(self):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return

        proxies = None
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb" if self.view.radio_javdb.isChecked() else "javbus"

        active_tasks = 0
        for file_path, info in self.task_files.items():
            code = info["code"]
            if not code or info["status"] in ["整理中...", "已整理成功"]:
                continue

            active_tasks += 1
            info["status"] = "整理中..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("整理中..."))

            # 执行整理落盘。如果已经缓存有元数据，直接传入 detail 免去重复请求
            worker = ScrapeWorker(file_path, code, output_dir, platform, proxies, only_scrape=False, cached_detail=info["detail"])
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)

            self.thread_pool.start(worker)

        if active_tasks == 0:
            QMessageBox.information(self.view, "提示", "列表中没有可整理落盘的影片")

    # ================== 后台线程信号槽 ==================
    def on_worker_started(self, filepath):
        if filepath in self.task_files:
            info = self.task_files[filepath]
            info["status"] = "开始执行"
            self.view.table.setItem(info["row"], 3, QTableWidgetItem("开始执行"))

    def on_worker_progress(self, filepath, message):
        if filepath in self.task_files:
            info = self.task_files[filepath]
            info["status"] = message
            self.view.table.setItem(info["row"], 3, QTableWidgetItem(message))

    def on_worker_preview_loaded(self, filepath, detail):
        # 缓存抓取到的元数据
        if filepath in self.task_files:
            self.task_files[filepath]["detail"] = detail
            
        # 如果当前选中了这一行，则立即刷新右侧预览
        selected_ranges = self.view.table.selectedRanges()
        if selected_ranges:
            current_row = selected_ranges[0].topRow()
            if filepath in self.task_files and self.task_files[filepath]["row"] == current_row:
                self.show_preview_details(detail, filepath)

    def on_worker_finished(self, filepath, status):
        if filepath in self.task_files:
            info = self.task_files[filepath]
            if status == "success":
                info["status"] = "已整理成功"
                self.view.table.setItem(info["row"], 3, QTableWidgetItem("已整理成功"))
                
                # 如果成功，且当前选中该行，加载本地已下载的海报和剧照展示
                selected_ranges = self.view.table.selectedRanges()
                if selected_ranges and selected_ranges[0].topRow() == info["row"]:
                    detail = info["detail"]
                    self.show_preview_details(detail, filepath, loaded_local=True)
            elif status == "scrape_success":
                info["status"] = "已刮削(未整理)"
                self.view.table.setItem(info["row"], 3, QTableWidgetItem("已刮削(未整理)"))
                
                # 如果成功，且当前选中该行，展示网络刮削详情预览
                selected_ranges = self.view.table.selectedRanges()
                if selected_ranges and selected_ranges[0].topRow() == info["row"]:
                    detail = info["detail"]
                    self.show_preview_details(detail, filepath, loaded_local=False)
            else:
                info["status"] = f"失败: {status}"
                self.view.table.setItem(info["row"], 3, QTableWidgetItem(f"失败: {status}"))

    def handle_selection_changed(self):
        selected_ranges = self.view.table.selectedRanges()
        if not selected_ranges:
            self.reset_preview_panel()
            return
            
        row = selected_ranges[0].topRow()
        filepath = None
        info = None
        for fp, task_info in self.task_files.items():
            if task_info["row"] == row:
                filepath = fp
                info = task_info
                break

        if not filepath or not info:
            self.reset_preview_panel()
            return

        detail = info["detail"]
        if detail:
            # 判断是否已经刮削成功并下载好本地图片
            is_success = info["status"] == "已整理成功"
            self.show_preview_details(detail, filepath, loaded_local=is_success)
        else:
            # 未刮削或刮削中，仅显示基础文件名信息
            self.reset_preview_panel()
            self.view.lbl_info_title.setText(f"本地影片:\n{os.path.basename(filepath)}")
            self.view.lbl_info_details.setText(f"当前状态: {info['status']}\n完整路径: {filepath}")

    def show_preview_details(self, detail: dict, filepath: str, loaded_local: bool = False):
        self.current_preview_filepath = filepath
        code = detail.get("code", "")
        title = detail.get("title", "")
        self.view.lbl_info_title.setText(f"[{code}]\n{title}")

        # 整理详情文本
        actors_str = ", ".join(detail.get("actors", [])) or "无"
        studio_str = detail.get("series", "") or detail.get("maker", "") or detail.get("publisher", "") or "无"
        date_str = detail.get("date", "") or "无"
        
        info_details_text = (
            f"片商: {studio_str}\n"
            f"发行日期: {date_str}\n"
            f"演员: {actors_str}\n\n"
            f"标签: {', '.join(detail.get('tags', []))}"
        )
        self.view.lbl_info_details.setText(info_details_text)

        # 渲染磁力链接表格
        self.view.table_magnet.setRowCount(0)
        magnets = detail.get("magnets", [])
        for mag in magnets:
            row = self.view.table_magnet.rowCount()
            self.view.table_magnet.insertRow(row)

            size_str = mag.get("size_text") or (f"{mag.get('size_mb', 0):.2f}MB" if mag.get('size_mb') else "未知大小")
            size_item = QTableWidgetItem(size_str)
            size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.view.table_magnet.setItem(row, 0, size_item)

            # 复制操作按钮
            btn_copy = QPushButton("复制")
            btn_copy.setObjectName("CopyMagnetBtn")
            magnet_link = mag.get("magnet", "")
            btn_copy.clicked.connect(lambda checked=False, link=magnet_link: self.copy_to_clipboard(link))
            self.view.table_magnet.setCellWidget(row, 1, btn_copy)

        # 渲染海报图片
        poster_loaded = False
        if loaded_local:
            output_dir = self.view.path_input.text().strip()
            clean_title = detail.get("title", "")
            for char in r'\/:*?"<>|':
                clean_title = clean_title.replace(char, " ")
            folder_name = f"[{code}] {clean_title}"[:120].strip()
            local_poster_path = os.path.join(output_dir, folder_name, "poster.jpg")
            
            if os.path.exists(local_poster_path):
                pixmap = QPixmap(local_poster_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(self.view.lbl_cover.width(), self.view.lbl_cover.height(),
                                                  Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.view.lbl_cover.setPixmap(scaled_pixmap)
                    poster_loaded = True

        if not poster_loaded:
            # 刮削中/未完成时直接使用网络地址预览海报
            cover_url = detail.get("cover_url")
            if cover_url:
                try:
                    proxies = None
                    if self.view.chk_custom_proxy.isChecked():
                        proxy = self.view.proxy_input.text().strip()
                        proxies = {"http": proxy, "https": proxy} if proxy else None
                    r = requests.get(cover_url, timeout=8, proxies=proxies)
                    if r.status_code == 200:
                        pixmap = QPixmap()
                        pixmap.loadFromData(r.content)
                        scaled_pixmap = pixmap.scaled(self.view.lbl_cover.width(), self.view.lbl_cover.height(),
                                                      Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.view.lbl_cover.setPixmap(scaled_pixmap)
                        poster_loaded = True
                except Exception as img_err:
                    self.view.lbl_cover.setText(f"封面加载失败\n{img_err}")
            
            if not poster_loaded:
                self.view.lbl_cover.setText("暂无封面")

        # 清空剧照 samples_layout
        if hasattr(self.view, "samples_layout"):
            while self.view.samples_layout.count():
                item = self.view.samples_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        # 渲染剧照样品预览
        if loaded_local:
            output_dir = self.view.path_input.text().strip()
            clean_title = detail.get("title", "")
            for char in r'\/:*?"<>|':
                clean_title = clean_title.replace(char, " ")
            folder_name = f"[{code}] {clean_title}"[:120].strip()
            local_folder = os.path.join(output_dir, folder_name)
            local_extrafanart_dir = os.path.join(local_folder, "extrafanart")
            
            if os.path.exists(local_extrafanart_dir):
                for file_name in sorted(os.listdir(local_extrafanart_dir)):
                    if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                        full_img_path = os.path.join(local_extrafanart_dir, file_name)
                        lbl = ClickableLabel()
                        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                        pix = QPixmap(full_img_path)
                        if not pix.isNull():
                            scaled_pix = pix.scaledToHeight(90, Qt.TransformationMode.SmoothTransformation)
                            lbl.setPixmap(scaled_pix)
                            lbl.pixmap_data = pix
                            lbl.clicked.connect(self.show_zoomed_image)
                            self.view.samples_layout.addWidget(lbl)
        else:
            # 网络异步加载剧照
            thumbnails = detail.get("thumbnail_images", [])
            if thumbnails:
                proxies = None
                if self.view.chk_custom_proxy.isChecked():
                    proxy = self.view.proxy_input.text().strip()
                    proxies = {"http": proxy, "https": proxy} if proxy else None
                # 跳过第一个封面图
                urls_to_load = thumbnails[1:] if len(thumbnails) > 1 else thumbnails
                for url in urls_to_load:
                    worker = ImageLoadWorker(filepath, url, proxies)
                    worker.signals.loaded.connect(self.on_network_image_loaded)
                    self.thread_pool.start(worker)

    def on_network_image_loaded(self, filepath, url, data):
        # 确保只有当前正在预览的视频才显示剧照，防错乱
        if self.current_preview_filepath == filepath:
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                lbl = ClickableLabel()
                lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                scaled_pix = pix.scaledToHeight(90, Qt.TransformationMode.SmoothTransformation)
                lbl.setPixmap(scaled_pix)
                lbl.pixmap_data = pix
                lbl.clicked.connect(self.show_zoomed_image)
                self.view.samples_layout.addWidget(lbl)

    def show_zoomed_image(self, pixmap):
        dialog = PhotoDialog(pixmap, self.view)
        dialog.exec()

    def copy_to_clipboard(self, text):
        if text:
            from PySide6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self.view, "提示", "磁力链接已成功复制到剪贴板！")
