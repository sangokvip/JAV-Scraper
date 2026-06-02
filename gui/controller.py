import os
import requests
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog
from PySide6.QtGui import QPixmap
from gui.main_window import MainWindow
from gui.scrape_worker import ScrapeWorker
from lib.code_extractor import extract_code

class Controller:
    def __init__(self, view: MainWindow):
        self.view = view
        self.thread_pool = QThreadPool.globalInstance()
        # 限制并发为 2，防止被平台封锁 IP
        self.thread_pool.setMaxThreadCount(2)
        
        # 存储所有正在排队或执行的任务文件：{file_path: {"code": str, "row": int, "detail": dict, "status": str}}
        self.task_files = {}

        # 默认保存路径为项目根目录下的 output 文件夹
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
        self.view.path_input.setText(default_out)

        # 信号槽绑定
        self.view.files_dropped.connect(self.handle_files_dropped)
        self.view.btn_browse.connect(self.browse_output_dir)
        self.view.btn_clear.connect(self.clear_all_tasks)
        self.view.btn_start.connect(self.start_scraping)
        self.view.btn_test_proxy.connect(self.test_proxy_connection)
        self.view.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.view.table.itemChanged.connect(self.handle_cell_changed)
        self.view.btn_save_cookie.connect(self.save_cookie_config)

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

    def test_proxy_connection(self):
        proxy = self.view.proxy_input.text().strip()
        self.view.lbl_proxy_status.setText("正在测试连接...")
        self.view.lbl_proxy_status.setStyleSheet("color: #E5C158;")
        
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            # 访问 JAVDB 验证连接
            r = requests.get("https://javdb.com", timeout=10, proxies=proxies)
            if r.status_code == 200:
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

        proxy = self.view.proxy_input.text().strip()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb" if self.view.radio_javdb.isChecked() else "javbus"

        active_tasks = 0
        for file_path, info in self.task_files.items():
            code = info["code"]
            if not code or info["status"] in ["正在刮削...", "刮削成功"]:
                continue

            active_tasks += 1
            info["status"] = "正在刮削..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("正在刮削..."))

            # 启动多线程任务
            worker = ScrapeWorker(file_path, code, output_dir, platform, proxies)
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)

            self.thread_pool.start(worker)

        if active_tasks == 0:
            QMessageBox.information(self.view, "提示", "列表中没有排队中的可刮削影片")

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
                info["status"] = "刮削成功"
                self.view.table.setItem(info["row"], 3, QTableWidgetItem("刮削成功"))
                
                # 如果成功，且当前选中该行，尝试加载本地已下载的海报 poster.jpg 进行展示
                selected_ranges = self.view.table.selectedRanges()
                if selected_ranges and selected_ranges[0].topRow() == info["row"]:
                    detail = info["detail"]
                    self.show_preview_details(detail, filepath, loaded_local=True)
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
            is_success = info["status"] == "刮削成功"
            self.show_preview_details(detail, filepath, loaded_local=is_success)
        else:
            # 未刮削或刮削中，仅显示基础文件名信息
            self.reset_preview_panel()
            self.view.lbl_info_title.setText(f"本地影片:\n{os.path.basename(filepath)}")
            self.view.lbl_info_details.setText(f"当前状态: {info['status']}\n完整路径: {filepath}")

    def show_preview_details(self, detail: dict, filepath: str, loaded_local: bool = False):
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

        # 渲染海报图片
        if loaded_local:
            # 刮削成功，大图已落盘在 [番号] 标题/poster.jpg
            output_dir = self.view.path_input.text().strip()
            clean_title = detail.get("title", "")
            for char in r'\/:*?"<>|':
                clean_title = clean_title.replace(char, " ")
            folder_name = f"[{code}] {clean_title}"[:120].strip()
            local_poster_path = os.path.join(output_dir, folder_name, "poster.jpg")
            
            if os.path.exists(local_poster_path):
                pixmap = QPixmap(local_poster_path)
                # 等比例缩放海报
                scaled_pixmap = pixmap.scaled(self.view.lbl_cover.width(), self.view.lbl_cover.height(),
                                              Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.view.lbl_cover.setPixmap(scaled_pixmap)
                return

        # 刮削中/未完成时直接使用网络地址预览
        cover_url = detail.get("cover_url")
        if cover_url:
            # 主线程异步下载以防卡死
            import urllib.request
            try:
                # 注意：网络拉取如果直接在主线程会略有卡顿，但用于单张预览可接受。也可以直接通过代理加载
                proxy = self.view.proxy_input.text().strip()
                proxies = {"http": proxy, "https": proxy} if proxy else None
                
                # 为保证极佳体验，我们通过 requests 快速获取
                r = requests.get(cover_url, timeout=5, proxies=proxies)
                if r.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(r.content)
                    scaled_pixmap = pixmap.scaled(self.view.lbl_cover.width(), self.view.lbl_cover.height(),
                                                  Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.view.lbl_cover.setPixmap(scaled_pixmap)
            except Exception as img_err:
                self.view.lbl_cover.setText(f"封面加载失败\n{img_err}")
        else:
            self.view.lbl_cover.setText("暂无封面")
