import os
import json
import requests
import config
from PySide6.QtCore import QThreadPool, Qt, Signal, QRunnable, QObject
from PySide6.QtWidgets import (
    QTableWidgetItem, QMessageBox, QFileDialog, QDialog, QVBoxLayout, 
    QHBoxLayout, QLabel, QTextEdit, QPushButton, QProgressBar, QWidget, QMenu
)
from PySide6.QtGui import QPixmap, QGuiApplication

from gui.main_window import MainWindow
from gui.scrape_worker import ScrapeWorker
from lib.code_extractor import extract_code
from gui.folder_cleaner import clean_empty_parent_dirs
from gui.task_persister import (
    save_tasks_backup, load_tasks_backup,
    save_settings_backup, load_settings_backup
)
from gui.widgets import (
    SortableTableWidgetItem, PhotoDialog, ClickableLabel, ConflictResolutionDialog,
    MultiCodeInputDialog
)
from gui.image_loader import ImageLoadWorker, SearchWorker

# 导入公共辅助类
from helpers.subtitle_helper import find_matching_subtitles
from helpers.duplicate_detector import find_existing_organized_folder
from helpers.player_helper import play_video, open_local_folder
from helpers.template_helper import format_target_path
class ProxyTestWorkerSignals(QObject):
    finished = Signal(bool, str)

class ProxyTestWorker(QRunnable):
    def __init__(self, proxy, timeout=8):
        super().__init__()
        self.proxy = proxy
        self.timeout = timeout
        self.signals = ProxyTestWorkerSignals()

    def run(self):
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        try:
            r = requests.get("https://www.google.com", timeout=self.timeout, proxies=proxies, headers=headers)
            if r.status_code == 200:
                self.signals.finished.emit(True, "连接正常 (OK)")
                return
        except Exception:
            pass

        target_url = "https://javdb.com"
        try:
            r = requests.get(target_url, timeout=self.timeout, proxies=proxies, headers=headers)
            if r.status_code in [200, 301, 302, 403]:
                self.signals.finished.emit(True, "连接正常 (OK)")
            else:
                self.signals.finished.emit(False, f"连接失败: 状态码 {r.status_code}")
        except Exception as e:
            self.signals.finished.emit(False, "连接超时/不可用")

class Controller:
    def __init__(self, view: MainWindow):
        self.view = view
        self.thread_pool = QThreadPool.globalInstance()
        
        # 专用的刮削线程池，限制并发为 1，防范高频并发被平台封锁 IP
        self.scrape_pool = QThreadPool()
        self.scrape_pool.setMaxThreadCount(1)
        
        # 存储所有正在排队或执行的任务文件：
        # {file_path: {"code": str, "row": int, "detail": dict, "status": str, "extra_files": list}}
        self.task_files = {}
        self.current_preview_filepath = None
        self.processed_parent_dirs = set()
        self.active_workers = set()
        self.running_scrape_workers = {}
        self.image_session = requests.Session()
        self.pixmap_cache = {}  # 强引用缩放图片缓存：(path_or_url, w, h) -> QPixmap

        # 信号槽绑定
        self.view.files_dropped.connect(self.handle_files_dropped)
        self.view.btn_browse.clicked.connect(self.browse_output_dir)
        self.view.btn_clear.clicked.connect(self.clear_all_tasks)
        self.view.drop_label.clicked.connect(self.import_files_manually)
        self.view.btn_import_dir.clicked.connect(self.import_dir_manually)
        self.view.btn_add_code.clicked.connect(self.add_code_manually)
        self.view.btn_start.clicked.connect(self.start_scraping)
        self.view.btn_organize.clicked.connect(self.start_organizing)
        self.view.btn_test_proxy.clicked.connect(self.test_proxy_connection)
        self.view.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.view.table.itemChanged.connect(self.handle_cell_changed)
        self.view.btn_save_cookie.clicked.connect(self.save_cookie_config)
        self.view.btn_remove_selected.clicked.connect(self.remove_selected_task)
        self.view.btn_retry_failed.clicked.connect(self.retry_failed_tasks)
        self.view.table.delete_pressed.connect(self.remove_selected_task)
        self.view.table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        
        # 搜索过滤联动信号
        self.view.search_input.textChanged.connect(self.apply_task_filter)
        self.view.filter_group.buttonClicked.connect(self.apply_task_filter)

        # 自动配置自动保存机制
        self.view.tmpl_input.textChanged.connect(self.save_settings)
        self.view.chk_download_samples.toggled.connect(self.save_settings)
        self.view.chk_subtitle_tag.toggled.connect(self.save_settings)
        self.view.chk_custom_proxy.toggled.connect(self.save_settings)
        self.view.proxy_input.textChanged.connect(self.save_settings)

        # 右键上下文菜单
        self.view.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.table.customContextMenuRequested.connect(self.show_table_context_menu)

        # 加载 Cookie & 配置 & 任务
        self.load_cookie_config()
        self.view.cookie_input.textChanged.connect(self.auto_save_cookie_config)
        self.load_settings()
        self.restore_backup_tasks()

    def save_backup(self):
        save_tasks_backup(self.task_files)

    def restore_backup_tasks(self):
        restored = load_tasks_backup()
        if not restored:
            self.view.update_empty_placeholder_visibility(True)
            return

        self.view.update_empty_placeholder_visibility(False)
        self.view.table.setRowCount(0)
        
        sorted_tasks = sorted(restored.items(), key=lambda x: x[1].get("row", 0))
        
        for filepath, info in sorted_tasks:
            row = self.view.table.rowCount()
            self.view.table.insertRow(row)

            info["row"] = row

            id_item = QTableWidgetItem(f"{row + 1:02d}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 0, id_item)

            extra_count = len(info.get("extra_files", []))
            if filepath.startswith("__virtual__"):
                name_text = "[无本地视频: 仅刮削元数据]"
            elif extra_count > 0:
                name_text = f"[多分段] {os.path.basename(filepath)} (+{extra_count}个文件)"
            else:
                name_text = os.path.basename(filepath)
                
            name_item = QTableWidgetItem(name_text)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 1, name_item)

            code_item = QTableWidgetItem(info.get("code", ""))
            self.view.table.setItem(row, 2, code_item)

            status_text = info.get("status", "等待中")
            if status_text in ("开始执行", "准备中") or status_text.startswith("正在"):
                status_text = "等待中"
                info["status"] = "等待中"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)

            self.task_files[filepath] = info

        if self.view.table.rowCount() > 0:
            self.view.table.selectRow(0)
        self.apply_task_filter()

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

        # 智能多 CD 番号分组算法
        grouped_files = {}
        ungrouped_files = []

        for file_path in all_files:
            # 避开已经在任务列表里的主文件或额外分段文件
            if file_path in self.task_files:
                continue
            is_already_extra = False
            for info in self.task_files.values():
                if file_path in info.get("extra_files", []):
                    is_already_extra = True
                    break
            if is_already_extra:
                continue

            code = extract_code(os.path.basename(file_path)) or ""
            if code:
                code_upper = code.strip().upper()
                grouped_files.setdefault(code_upper, []).append(file_path)
            else:
                ungrouped_files.append(file_path)

        added_primary_files = []

        # 1. 导入有号码的影片分组
        for code, file_list in grouped_files.items():
            # 检查当前任务列表中是否已有该番号
            existing_primary_path = None
            for fp, info in self.task_files.items():
                if info.get("code") == code:
                    existing_primary_path = fp
                    break

            if existing_primary_path:
                # 累加到现有任务的分段中
                info = self.task_files[existing_primary_path]
                for f in file_list:
                    if f != existing_primary_path and f not in info["extra_files"]:
                        info["extra_files"].append(f)
                # 更新 UI 的原文件名显示
                row = info["row"]
                extra_count = len(info["extra_files"])
                name_text = f"[多分段] {os.path.basename(existing_primary_path)} (+{extra_count}个文件)"
                self.view.table.item(row, 1).setText(name_text)
            else:
                # 创建新组合任务
                file_list.sort()
                primary_path = file_list[0]
                extra_files = file_list[1:]
                
                row = self.view.table.rowCount()
                self.view.table.insertRow(row)

                id_item = QTableWidgetItem(f"{row + 1:02d}")
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.view.table.setItem(row, 0, id_item)

                extra_count = len(extra_files)
                name_text = f"[多分段] {os.path.basename(primary_path)} (+{extra_count}个文件)" if extra_count > 0 else os.path.basename(primary_path)
                name_item = QTableWidgetItem(name_text)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.view.table.setItem(row, 1, name_item)

                code_item = QTableWidgetItem(code)
                self.view.table.setItem(row, 2, code_item)

                status_item = QTableWidgetItem("正在刮削...")
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.view.table.setItem(row, 3, status_item)

                self.task_files[primary_path] = {
                    "code": code,
                    "row": row,
                    "detail": None,
                    "status": "正在刮削...",
                    "extra_files": extra_files
                }
                added_primary_files.append(primary_path)

        # 2. 导入无号码的普通影片
        for file_path in ungrouped_files:
            row = self.view.table.rowCount()
            self.view.table.insertRow(row)

            id_item = QTableWidgetItem(f"{row + 1:02d}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 0, id_item)

            name_item = QTableWidgetItem(os.path.basename(file_path))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 1, name_item)

            code_item = QTableWidgetItem("")
            self.view.table.setItem(row, 2, code_item)

            status_item = QTableWidgetItem("番号待补充")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)

            self.task_files[file_path] = {
                "code": "",
                "row": row,
                "detail": None,
                "status": "番号待补充",
                "extra_files": []
            }

        # 自动触发多线程刮削
        if added_primary_files:
            first_info = self.task_files[added_primary_files[0]]
            self.view.table.selectRow(first_info["row"])

            output_dir = self.view.path_input.text().strip()
            if output_dir:
                proxies = self.get_active_proxies()
                for fp in added_primary_files:
                    worker = ScrapeWorker(fp, self.task_files[fp]["code"], output_dir, "javdb", proxies, only_scrape=True)
                    self.start_worker(worker)

        self.save_backup()
        self.view.update_empty_placeholder_visibility(len(self.task_files) == 0)
        self.apply_task_filter()

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
        dialog = MultiCodeInputDialog(self.view)
        
        # 绑定搜索请求到主控制器的后台线程查询
        dialog.search_requested.connect(lambda keyword, page: self.handle_dialog_search(keyword, page, dialog))
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            codes = dialog.get_entered_codes()
            if not codes:
                return
            output_dir = self.view.path_input.text().strip()
            proxies = self.get_active_proxies()
            added_any = False
            first_row = None
            
            for code in codes:
                virtual_path = f"__virtual__:{code}"
                if virtual_path in self.task_files:
                    continue
                row = self.view.table.rowCount()
                self.view.table.insertRow(row)
                if first_row is None:
                    first_row = row
                id_item = QTableWidgetItem(f"{row + 1:02d}")
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.view.table.setItem(row, 0, id_item)
                name_item = QTableWidgetItem("[无本地视频: 仅刮削元数据]")
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.view.table.setItem(row, 1, name_item)
                code_item = QTableWidgetItem(code)
                self.view.table.setItem(row, 2, code_item)
                status_item = QTableWidgetItem("正在刮削...")
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.view.table.setItem(row, 3, status_item)
                
                self.task_files[virtual_path] = {
                    "code": code,
                    "row": row,
                    "detail": None,
                    "status": "正在刮削...",
                    "extra_files": []
                }
                if output_dir:
                    worker = ScrapeWorker(virtual_path, code, output_dir, "javdb", proxies, only_scrape=True)
                    self.start_worker(worker)
                added_any = True
            if added_any:
                if first_row is not None:
                    self.view.table.selectRow(first_row)
                self.save_backup()
                self.view.update_empty_placeholder_visibility(False)
                self.apply_task_filter()

    def handle_dialog_search(self, keyword: str, page: int, dialog):
        dialog.set_search_loading(True)
        proxies = self.get_active_proxies()
        cookie_string = self.view.cookie_input.text().strip()
        worker = SearchWorker(keyword, page, proxies, cookie_string)
        
        # 禁用后台线程自动析构，并加入强引用集合中以防意外垃圾回收
        worker.setAutoDelete(False)
        self.active_workers.add(worker)
        
        def on_search_finished(codes, error_msg):
            dialog.set_search_loading(False)
            if error_msg:
                dialog.lbl_search_status.setText(f"搜索失败: {error_msg}")
                dialog.lbl_search_status.setStyleSheet("color: #FF453A; font-weight: bold; background-color: transparent;")
            else:
                dialog.add_searched_codes(codes)
                
        worker.signals.finished.connect(on_search_finished)
        worker.signals.finished_worker.connect(self.on_worker_destroyed)
        self.thread_pool.start(worker)

    def handle_cell_changed(self, item):
        if item.column() == 2:
            row = item.row()
            target_fp = None
            new_code = None
            for fp, info in self.task_files.items():
                if info["row"] == row:
                    new_code = item.text().strip().upper()
                    self.view.table.blockSignals(True)
                    item.setText(new_code)
                    self.view.table.blockSignals(False)
                    info["code"] = new_code
                    target_fp = fp
                    break
            
            if target_fp and new_code:
                info = self.task_files[target_fp]
                info["status"] = "正在刮削..."
                
                status_item = self.view.table.item(row, 3)
                if status_item:
                    status_item.setText("正在刮削...")
                
                self.save_backup()
                
                output_dir = self.view.path_input.text().strip()
                if output_dir:
                    proxies = self.get_active_proxies()
                    worker = ScrapeWorker(target_fp, new_code, output_dir, "javdb", proxies, only_scrape=True)
                    self.start_worker(worker)
            elif target_fp:
                info = self.task_files[target_fp]
                info["status"] = "番号待补充"
                status_item = self.view.table.item(row, 3)
                if status_item:
                    status_item.setText("番号待补充")
                self.save_backup()
            self.apply_task_filter()

    def handle_cell_double_clicked(self, row, column):
        # 排除“识别番号”编辑列。其他列双击则调用视频播放
        if column != 2:
            filepath = None
            for fp, info in self.task_files.items():
                if info["row"] == row:
                    filepath = fp
                    break
            if filepath:
                self.play_task_video(filepath)

    def apply_task_filter(self):
        """
        实时过滤算法，实现搜索输入框和状态药丸的交集隐显过滤。
        """
        search_txt = self.view.search_input.text().strip().upper()
        filter_id = self.view.filter_group.checkedId()
        
        visible_row_count = 0
        
        for fp, info in self.task_files.items():
            row = info["row"]
            code = info["code"].upper()
            filename = os.path.basename(fp).upper()
            status = info["status"]
            
            # 搜索框匹配
            matches_search = (not search_txt) or (search_txt in code) or (search_txt in filename)
            
            # 分类过滤匹配
            matches_filter = True
            if filter_id == 1:    # 待整理
                matches_filter = status in ("等待中", "已刮削(未整理)", "番号待补充")
            elif filter_id == 2:  # 进行中
                matches_filter = status in ("开始执行", "准备中") or status.startswith("正在") or status.endswith("中...")
            elif filter_id == 3:  # 已成功
                matches_filter = status == "已整理成功"
            elif filter_id == 4:  # 失败项
                matches_filter = "失败" in status or "异常" in status or status.startswith("❌")
                
            is_visible = matches_search and matches_filter
            self.view.table.setRowHidden(row, not is_visible)
            if is_visible:
                visible_row_count += 1
                
        # 更新列表是否为空占位盘
        is_empty = len(self.task_files) == 0
        self.view.update_empty_placeholder_visibility(is_empty)

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self.view, "选择保存目标文件夹")
        if dir_path:
            abs_path = os.path.abspath(dir_path)
            self.view.path_input.setText(abs_path)
            self.save_settings()

    def save_settings(self):
        settings = {
            "output_dir": self.view.path_input.text().strip(),
            "rename_template": self.view.tmpl_input.text().strip(),
            "download_samples": self.view.chk_download_samples.isChecked(),
            "write_subtitle_tag": self.view.chk_subtitle_tag.isChecked(),
            "custom_proxy": self.view.chk_custom_proxy.isChecked(),
            "proxy_url": self.view.proxy_input.text().strip()
        }
        save_settings_backup(settings)

    def load_settings(self):
        settings = load_settings_backup()
        self.view.path_input.setText(settings.get("output_dir", str(config.OUTPUT_DIR['root'])))
        self.view.tmpl_input.setText(settings.get("rename_template", "{actor}/{[code]} {title}"))
        self.view.chk_download_samples.setChecked(settings.get("download_samples", True))
        self.view.chk_subtitle_tag.setChecked(settings.get("write_subtitle_tag", True))
        self.view.chk_custom_proxy.setChecked(settings.get("custom_proxy", False))
        self.view.proxy_input.setText(settings.get("proxy_url", "http://127.0.0.1:10808"))

    def get_active_proxies(self) -> dict or None:
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            return {"http": proxy, "https": proxy} if proxy else None
        return None

    def start_worker(self, worker):
        fp = worker.file_path
        if fp in self.running_scrape_workers:
            old_worker = self.running_scrape_workers[fp]
            old_worker.is_cancelled = True
            try:
                old_worker.signals.started.disconnect()
                old_worker.signals.progress.disconnect()
                old_worker.signals.preview_loaded.disconnect()
                old_worker.signals.finished.disconnect()
                old_worker.signals.finished_worker.disconnect()
            except Exception:
                pass
            self.running_scrape_workers.pop(fp, None)

        worker.setAutoDelete(False)
        worker.signals.started.connect(self.on_worker_started)
        worker.signals.progress.connect(self.on_worker_progress)
        worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.finished_worker.connect(self.on_worker_destroyed)
        self.active_workers.add(worker)
        self.running_scrape_workers[fp] = worker
        self.scrape_pool.start(worker)

    def clear_all_tasks(self):
        # 立即取消所有运行中的 worker 并断开信号连接
        for fp, worker in list(self.running_scrape_workers.items()):
            worker.is_cancelled = True
            try:
                worker.signals.started.disconnect()
                worker.signals.progress.disconnect()
                worker.signals.preview_loaded.disconnect()
                worker.signals.finished.disconnect()
                worker.signals.finished_worker.disconnect()
            except Exception:
                pass
        self.running_scrape_workers.clear()

        self.view.table.setRowCount(0)
        self.task_files.clear()
        self.pixmap_cache.clear()
        self.current_preview_filepath = None
        self.reset_preview_panel()
        self.save_backup()
        self.view.update_empty_placeholder_visibility(True)

    def remove_selected_task(self):
        selected_rows = set()
        for range_obj in self.view.table.selectedRanges():
            for r in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                selected_rows.add(r)
                
        if not selected_rows:
            return
            
        sorted_rows = sorted(list(selected_rows), reverse=True)
        
        for row in sorted_rows:
            target_fp = None
            for fp, info in self.task_files.items():
                if info["row"] == row:
                    target_fp = fp
                    break
            
            if target_fp:
                if target_fp in self.running_scrape_workers:
                    worker = self.running_scrape_workers[target_fp]
                    worker.is_cancelled = True
                    try:
                        worker.signals.started.disconnect()
                        worker.signals.progress.disconnect()
                        worker.signals.preview_loaded.disconnect()
                        worker.signals.finished.disconnect()
                        worker.signals.finished_worker.disconnect()
                    except Exception:
                        pass
                    self.running_scrape_workers.pop(target_fp, None)

                if target_fp in self.task_files:
                    del self.task_files[target_fp]
                self.view.table.removeRow(row)
                
                # 整理后续 row 索引偏移
                for fp, info in self.task_files.items():
                    if info["row"] > row:
                        info["row"] -= 1

        for r in range(self.view.table.rowCount()):
            id_item = self.view.table.item(r, 0)
            if id_item:
                id_item.setText(f"{r + 1:02d}")

        # 删除完成后，若当前预览项已不在任务列表中（含列表已清空的情况），则重置右侧面板
        if self.current_preview_filepath not in self.task_files:
            self.reset_preview_panel()
            self.current_preview_filepath = None
            
        self.save_backup()
        self.apply_task_filter()

    def show_table_context_menu(self, pos):
        item = self.view.table.itemAt(pos)
        if not item:
            return
            
        row = item.row()
        selected_rows = set()
        for range_obj in self.view.table.selectedRanges():
            for r in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                selected_rows.add(r)
                
        if row not in selected_rows:
            self.view.table.selectRow(row)
            selected_rows = {row}
            
        selected_fps = []
        for r in selected_rows:
            for fp, info in self.task_files.items():
                if info["row"] == r:
                    selected_fps.append(fp)
                    break
                    
        if not selected_fps:
            return
            
        count = len(selected_fps)
        menu = QMenu(self.view)
        
        # 菜单的美化白金橙样式
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                color: #1A1C2E;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(255, 89, 36, 0.08);
                color: #FF5924;
            }
            QMenu::item:disabled {
                color: #C0C4CC;
            }
        """)
        
        # 单/多影片的整理控制
        if count > 1:
            action_scrape = menu.addAction(f"仅刮削选中的影片 ({count}部)")
            action_organize = menu.addAction(f"仅整理选中的影片 ({count}部)")
            menu.addSeparator()
            action_remove = menu.addAction(f"从列表中移除选中的影片 ({count}部)")
        else:
            action_scrape = menu.addAction("仅刮削此影片")
            action_organize = menu.addAction("仅整理此影片")
            # 引入直接播放
            filepath = selected_fps[0]
            is_organized = self.task_files[filepath]["status"] == "已整理成功"
            
            action_play = menu.addAction("播放归档影片")
            action_open = menu.addAction("在 Finder 中打开文件夹")
            action_play.setEnabled(is_organized)
            action_open.setEnabled(is_organized)
            
            menu.addSeparator()
            action_remove = menu.addAction("从列表中移除")
            
        any_has_code = any(self.task_files[fp]["code"] for fp in selected_fps)
        any_running = any(self.task_files[fp]["status"] in ["正在刮削...", "整理中..."] for fp in selected_fps)
        
        if not any_has_code or any_running:
            action_scrape.setEnabled(False)
            action_organize.setEnabled(False)
            
        global_pos = self.view.table.viewport().mapToGlobal(pos)
        selected_action = menu.exec(global_pos)
        
        if selected_action == action_scrape:
            self.scrape_multiple_tasks(selected_fps)
        elif selected_action == action_organize:
            self.organize_multiple_tasks(selected_fps)
        elif selected_action == action_remove:
            self.remove_selected_task()
        elif count == 1 and selected_action == action_play:
            self.play_task_video(selected_fps[0])
        elif count == 1 and selected_action == action_open:
            self.open_task_folder(selected_fps[0])

    def play_task_video(self, filepath):
        video_path = self.get_organized_video_path(filepath)
        if video_path and os.path.exists(video_path):
            play_video(video_path)
        else:
            QMessageBox.warning(self.view, "提示", "找不到对应的本地已归档视频文件。")

    def open_task_folder(self, filepath):
        video_path = self.get_organized_video_path(filepath)
        if video_path and os.path.exists(video_path):
            open_local_folder(video_path)
        else:
            # 尝试直接打开算出路径下的根文件夹
            info = self.task_files.get(filepath)
            if info and info.get("detail"):
                output_dir = self.view.path_input.text().strip()
                tmpl = self.view.tmpl_input.text().strip()
                target_folder = format_target_path(tmpl, output_dir, info["code"], info["detail"])
                if os.path.exists(target_folder):
                    open_local_folder(target_folder)
                    return
            QMessageBox.warning(self.view, "提示", "归档目录尚未创建。")

    def get_organized_video_path(self, filepath) -> str or None:
        info = self.task_files.get(filepath)
        if not info or not info.get("detail"):
            return None
        output_dir = self.view.path_input.text().strip()
        tmpl = self.view.tmpl_input.text().strip()
        target_folder = format_target_path(tmpl, output_dir, info["code"], info["detail"])
        if not os.path.isdir(target_folder):
            return None
        
        # 寻找匹配的视频
        valid_extensions = ('.mp4', '.mkv', '.avi', '.wmv', '.mov', '.flv', '.rmvb')
        try:
            for entry in os.listdir(target_folder):
                if entry.lower().endswith(valid_extensions) and info["code"].upper() in entry.upper():
                    return os.path.join(target_folder, entry)
        except Exception:
            pass
        return None

    def scrape_multiple_tasks(self, file_paths):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return
            
        proxies = self.get_active_proxies()
        
        for fp in file_paths:
            info = self.task_files.get(fp)
            if not info or not info["code"] or info["status"] in ["正在刮削...", "整理中..."]:
                continue
                
            info["status"] = "正在刮削..."
            self.view.table.setItem(info["row"], 3, QTableWidgetItem("正在刮削..."))
            
            worker = ScrapeWorker(fp, info["code"], output_dir, "javdb", proxies, only_scrape=True, use_reverse_proxy=self.view.chk_use_reverse_proxy.isChecked())
            self.start_worker(worker)
        self.save_backup()
        self.apply_task_filter()

    def organize_multiple_tasks(self, file_paths):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return
            
        todo_files = []
        for fp in file_paths:
            info = self.task_files.get(fp)
            if not info or not info["code"] or info["status"] == "整理中...":
                continue
            todo_files.append(fp)
            
        if not todo_files:
            return

        # 1. 冲突预检并弹出抉择框
        conflict_resolution = self.pre_check_conflicts_and_prompt(todo_files, output_dir)
        if conflict_resolution is None:
            return  # 取消整理

        proxies = self.get_active_proxies()
        rename_tmpl = self.view.tmpl_input.text().strip()
        download_samples = self.view.chk_download_samples.isChecked()
        write_sub_tag = self.view.chk_subtitle_tag.isChecked()
        
        for fp in todo_files:
            info = self.task_files.get(fp)
            info["status"] = "整理中..."
            self.view.table.setItem(info["row"], 3, QTableWidgetItem("整理中..."))
            
            worker = ScrapeWorker(fp, info["code"], output_dir, "javdb", proxies, only_scrape=False, 
                                 cached_detail=info["detail"], extra_files=info.get("extra_files", []),
                                 rename_template=rename_tmpl, download_samples=download_samples,
                                 write_subtitle_tag=write_sub_tag, conflict_resolution=conflict_resolution)
            self.start_worker(worker)
        self.save_backup()
        self.apply_task_filter()

    def pre_check_conflicts_and_prompt(self, file_paths: list, output_dir: str) -> str or None:
        """
        进行整理前的番号归档防重冲突校验。
        """
        has_virtual = any(fp.startswith("__virtual__:") for fp in file_paths)
        if has_virtual:
            reply = QMessageBox.question(
                self.view, "提示",
                "包含手动输入番号的虚拟影片，本地并无视频文件。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return None

        # 扫描重名目录
        conflicts = []
        for fp in file_paths:
            info = self.task_files.get(fp)
            if info and info["code"] and info.get("detail"):
                existing = find_existing_organized_folder(output_dir, info["code"])
                if existing:
                    conflicts.append((fp, info["code"], existing))

        if conflicts:
            dialog = ConflictResolutionDialog(conflicts, self.view)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return dialog.selected_resolution()
            else:
                return None  # 取消执行整理
        
        return "keep_both"  # 无冲突时，默认保留两者机制

    def start_scraping(self):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return

        todo_files = []
        done_files = []
        for fp, info in self.task_files.items():
            if not info["code"]:
                continue
            if info["status"] in ["正在刮削...", "整理中..."]:
                continue
            if info["status"] in ["已刮削(未整理)", "已整理成功"]:
                done_files.append(fp)
            else:
                todo_files.append(fp)

        if not todo_files and not done_files:
            QMessageBox.information(self.view, "提示", "列表中没有可以刮削的影片")
            return

        if not todo_files and done_files:
            reply = QMessageBox.question(
                self.view, "重新刮削提示",
                "所选影片均已刮削，是否重新刮削？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                todo_files = done_files
            else:
                return

        proxies = self.get_active_proxies()
        for fp in todo_files:
            info = self.task_files[fp]
            info["status"] = "正在刮削..."
            self.view.table.setItem(info["row"], 3, QTableWidgetItem("正在刮削..."))
            
            worker = ScrapeWorker(fp, info["code"], output_dir, "javdb", proxies, only_scrape=True, use_reverse_proxy=self.view.chk_use_reverse_proxy.isChecked())
            self.start_worker(worker)
        self.save_backup()
        self.apply_task_filter()

    def start_organizing(self):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return

        todo_files = []
        done_files = []
        for fp, info in self.task_files.items():
            if not info["code"]:
                continue
            if info["status"] == "整理中...":
                continue
            if info["status"] == "已整理成功":
                done_files.append(fp)
            else:
                todo_files.append(fp)

        if not todo_files and not done_files:
            QMessageBox.information(self.view, "提示", "列表中没有可以整理的视频")
            return

        if not todo_files and done_files:
            reply = QMessageBox.question(
                self.view, "重新整理提示",
                "所选影片均已整理成功，是否要重新整理？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                todo_files = done_files
            else:
                return

        # 冲突与虚拟任务预检
        resolution = self.pre_check_conflicts_and_prompt(todo_files, output_dir)
        if resolution is None:
            return  # 取消

        proxies = self.get_active_proxies()
        rename_tmpl = self.view.tmpl_input.text().strip()
        download_samples = self.view.chk_download_samples.isChecked()
        write_sub_tag = self.view.chk_subtitle_tag.isChecked()

        for fp in todo_files:
            info = self.task_files[fp]
            info["status"] = "整理中..."
            self.view.table.setItem(info["row"], 3, QTableWidgetItem("整理中..."))

            worker = ScrapeWorker(fp, info["code"], output_dir, "javdb", proxies, only_scrape=False, 
                                 cached_detail=info["detail"], extra_files=info.get("extra_files", []),
                                 rename_template=rename_tmpl, download_samples=download_samples,
                                 write_subtitle_tag=write_sub_tag, conflict_resolution=resolution)
            self.start_worker(worker)
        self.save_backup()
        self.apply_task_filter()

    # ================== 后台线程信号槽 ==================
    def on_worker_destroyed(self, worker):
        self.active_workers.discard(worker)
        fp = getattr(worker, 'file_path', None)
        if fp and self.running_scrape_workers.get(fp) == worker:
            self.running_scrape_workers.pop(fp, None)

    def on_worker_started(self, filepath):
        if filepath not in self.task_files:
            return
        info = self.task_files[filepath]
        row = info.get("row", -1)
        if row < 0 or row >= self.view.table.rowCount():
            return
        info["status"] = "开始执行"
        try:
            self.view.table.removeCellWidget(row, 3)
            self.view.table.setItem(row, 3, QTableWidgetItem("开始执行"))
            self.save_backup()
            self.apply_task_filter()
        except Exception as e:
            print(f"Error on_worker_started: {e}")

    def on_worker_progress(self, filepath, message):
        if filepath not in self.task_files:
            return
        info = self.task_files[filepath]
        info["status"] = message
        row = info.get("row", -1)
        if row < 0 or row >= self.view.table.rowCount():
            return
            
        import re
        match = re.search(r"\((\d+)/(\d+)\)", message)
        try:
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                
                widget = self.view.table.cellWidget(row, 3)
                if not widget:
                    self.view.table.setItem(row, 3, QTableWidgetItem(""))
                    widget = QWidget()
                    layout = QVBoxLayout(widget)
                    layout.setContentsMargins(5, 2, 5, 2)
                    layout.setSpacing(2)
                    
                    lbl = QLabel(message)
                    lbl.setStyleSheet("color: #1A1C2E; font-size: 11px; font-weight: normal; background-color: transparent;")
                    lbl.setObjectName("ProgressLabel")
                    
                    bar = QProgressBar()
                    bar.setObjectName("ProgressBar")
                    bar.setRange(0, total)
                    bar.setValue(current)
                    bar.setTextVisible(False)
                    bar.setStyleSheet("""
                        QProgressBar {
                            border: 1px solid #E5EAF2;
                            border-radius: 3px;
                            background-color: #F0F2F5;
                            height: 6px;
                        }
                        QProgressBar::chunk {
                            background-color: #FF5924;
                            border-radius: 2px;
                        }
                    """)
                    
                    layout.addWidget(lbl)
                    layout.addWidget(bar)
                    widget.setLayout(layout)
                    self.view.table.setCellWidget(row, 3, widget)
                else:
                    lbl = widget.findChild(QLabel, "ProgressLabel")
                    bar = widget.findChild(QProgressBar, "ProgressBar")
                    if lbl:
                        lbl.setText(message)
                    if bar:
                        bar.setRange(0, total)
                        bar.setValue(current)
            else:
                self.view.table.removeCellWidget(row, 3)
                self.view.table.setItem(row, 3, QTableWidgetItem(message))
        except Exception as e:
            print(f"Error on_worker_progress: {e}")

    def on_worker_preview_loaded(self, filepath, detail):
        if filepath not in self.task_files:
            return
        self.task_files[filepath]["detail"] = detail
        
        self.save_backup()

        selected_ranges = self.view.table.selectedRanges()
        if selected_ranges:
            current_row = selected_ranges[0].topRow()
            row = self.task_files[filepath].get("row", -1)
            if row == current_row and 0 <= row < self.view.table.rowCount():
                try:
                    self.show_preview_details(detail, filepath)
                except Exception as e:
                    print(f"Error show_preview_details in preview_loaded: {e}")

    def on_worker_finished(self, filepath, status):
        if filepath not in self.task_files:
            return
        info = self.task_files[filepath]
        row = info.get("row", -1)
        if 0 <= row < self.view.table.rowCount():
            try:
                self.view.table.removeCellWidget(row, 3)
                if status == "success":
                    info["status"] = "已整理成功"
                    self.view.table.setItem(row, 3, QTableWidgetItem("✅ 已整理成功"))
                    
                    selected_ranges = self.view.table.selectedRanges()
                    if selected_ranges and selected_ranges[0].topRow() == row:
                        detail = info["detail"]
                        self.show_preview_details(detail, filepath, loaded_local=True)
                    
                    if not filepath.startswith("__virtual__:"):
                        parent_dir = os.path.dirname(filepath)
                        self.processed_parent_dirs.add(parent_dir)
                        # 联动分段文件目录
                        for extra_f in info.get("extra_files", []):
                            self.processed_parent_dirs.add(os.path.dirname(extra_f))
                elif status == "scrape_success":
                    info["status"] = "已刮削(未整理)"
                    self.view.table.setItem(row, 3, QTableWidgetItem("已刮削(未整理)"))
                    
                    selected_ranges = self.view.table.selectedRanges()
                    if selected_ranges and selected_ranges[0].topRow() == row:
                        detail = info["detail"]
                        self.show_preview_details(detail, filepath, loaded_local=False)
                elif status == "cancelled":
                    info["status"] = "已取消"
                    self.view.table.setItem(row, 3, QTableWidgetItem("已取消"))
                else:
                    info["status"] = f"失败: {status}"
                    self.view.table.setItem(row, 3, QTableWidgetItem(f"❌ 失败: {status}"))
                
                self.save_backup()
                self.apply_task_filter()
            except Exception as e:
                print(f"Error updating UI in on_worker_finished: {e}")

        # 检查是否所有正在执行的任务都已执行完毕
        all_done = True
        for fp, t_info in self.task_files.items():
            s = t_info.get("status", "")
            if s in ("开始执行", "准备中") or s.startswith("正在"):
                all_done = False
                break

        if all_done and self.processed_parent_dirs:
            empty_dirs = clean_empty_parent_dirs(self.processed_parent_dirs)
            if empty_dirs:
                dir_list_str = "\n".join(empty_dirs)
                reply = QMessageBox.question(
                    self.view,
                    "清理空文件夹",
                    f"以下原视频所在的文件夹在整理后已变为空，是否删除它们？\n\n{dir_list_str}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    import shutil
                    for pdir in empty_dirs:
                        try:
                            shutil.rmtree(pdir)
                        except Exception as e:
                            print(f"删除文件夹失败 {pdir}: {e}")
            self.processed_parent_dirs.clear()
            self.save_backup()

    def handle_selection_changed(self):
        selected_ranges = self.view.table.selectedRanges()
        if not selected_ranges:
            self.reset_preview_panel()
            return
            
        row = self.view.table.currentRow()
        if row < 0:
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
            is_success = info["status"] == "已整理成功"
            self.show_preview_details(detail, filepath, loaded_local=is_success)
        else:
            self.reset_preview_panel()
            self.view.lbl_info_title.setText(
                f"<div style='margin-top: 10px;'>"
                f"  <span style='color: #748297; font-size: 11px; font-weight: bold; background-color: #F0F2F5; padding: 2px 6px; border-radius: 3px;'>本地影片</span>"
                f"  <div style='color: #1A1C2E; font-size: 13px; font-weight: bold; margin-top: 6px; line-height: 1.35;'>{os.path.basename(filepath)}</div>"
                f"</div>"
            )
            self.view.lbl_info_details.setText(f"当前状态: {info['status']}\n完整路径: {filepath}")

    def show_preview_details(self, detail: dict, filepath: str, loaded_local: bool = False):
        self.current_preview_filepath = filepath
        code = detail.get("code", "")
        title = detail.get("title", "")
        self.view.lbl_info_title.setText(
            f"<div style='margin-top: 10px;'>"
            f"  <span style='color: #FF5924; font-size: 11px; font-weight: bold; background-color: #FFF1F1; padding: 3px 10px; border-radius: 12px; border: 1.5px solid #FF5924;'>{code}</span>"
            f"  <div style='color: #1A1C2E; font-family: Lora, Georgia, serif; font-style: italic; font-size: 15px; font-weight: 500; margin-top: 10px; line-height: 1.35;'>{title}</div>"
            f"</div>"
        )

        actors_str = ", ".join(detail.get("actors", [])) or "无"
        studio_str = detail.get("series", "") or detail.get("maker", "") or detail.get("publisher", "") or "无"
        date_str = detail.get("date", "") or "无"
        
        info_details_text = (
            f"片商: {studio_str}\n"
            f"发行日期: {date_str}\n"
            f"演员: {actors_str}\n\n"
        )
        if not filepath.startswith("__virtual__:"):
            if loaded_local:
                output_dir = self.view.path_input.text().strip()
                tmpl = self.view.tmpl_input.text().strip()
                target_folder = format_target_path(tmpl, output_dir, code, detail)
                info_details_text += f"整理后路径: {target_folder}\n\n"
            else:
                info_details_text += f"原文件路径: {filepath}\n\n"
                # 显示附加的分段信息
                extra_files = self.task_files[filepath].get("extra_files", [])
                if extra_files:
                    info_details_text += f"包含其他分段 ({len(extra_files)}个):\n"
                    for ext_f in extra_files:
                        info_details_text += f"  - {os.path.basename(ext_f)}\n"
                    info_details_text += "\n"
            
        info_details_text += f"标签: {', '.join(detail.get('tags', []))}"
        self.view.lbl_info_details.setText(info_details_text)

        # 渲染磁力表格
        self.view.table_magnet.setSortingEnabled(False)
        self.view.table_magnet.setRowCount(0)
        
        magnets = detail.get("magnets", [])
        import re
        for mag in magnets:
            row = self.view.table_magnet.rowCount()
            self.view.table_magnet.insertRow(row)

            magnet_link = mag.get("magnet") or mag.get("link") or ""

            if "magnet" in mag:
                size_text = mag.get("size_text") or "未知大小"
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', size_text)
                if date_match:
                    d_str = date_match.group(0)
                    size_str = size_text.replace(d_str, "").strip(", ")
                else:
                    d_str = "-"
                    size_str = size_text
                size_mb = mag.get("size_mb") or self._parse_size_mb(size_str)
            else:
                size_str = mag.get("size") or "未知大小"
                d_str = mag.get("share_date") or "-"
                size_mb = self._parse_size_mb(size_str)

            size_item = SortableTableWidgetItem(size_str, size_mb)
            size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.view.table_magnet.setItem(row, 0, size_item)

            date_item = SortableTableWidgetItem(d_str, d_str)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.view.table_magnet.setItem(row, 1, date_item)

            btn_copy = QPushButton("复制")
            btn_copy.setObjectName("CopyMagnetBtn")
            btn_copy.clicked.connect(lambda checked=False, link=magnet_link: self.copy_to_clipboard(link))
            self.view.table_magnet.setCellWidget(row, 2, btn_copy)

        self.view.table_magnet.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.view.table_magnet.setSortingEnabled(True)

        # 渲染海报图片
        poster_loaded = False
        w, h = self.view.lbl_cover.width(), self.view.lbl_cover.height()

        if loaded_local:
            output_dir = self.view.path_input.text().strip()
            tmpl = self.view.tmpl_input.text().strip()
            local_poster_path = os.path.join(format_target_path(tmpl, output_dir, code, detail), "poster.jpg")
            
            cache_key = (local_poster_path, w, h)
            if cache_key in self.pixmap_cache:
                self.view.lbl_cover.setPixmap(self.pixmap_cache[cache_key])
                poster_loaded = True
            elif os.path.exists(local_poster_path):
                pixmap = QPixmap(local_poster_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.pixmap_cache[cache_key] = scaled_pixmap
                    self.view.lbl_cover.setPixmap(scaled_pixmap)
                    poster_loaded = True

        if not poster_loaded:
            cover_url = detail.get("cover_url")
            if cover_url:
                cache_key = (cover_url, w, h)
                if cache_key in self.pixmap_cache:
                    self.view.lbl_cover.setPixmap(self.pixmap_cache[cache_key])
                    poster_loaded = True
                else:
                    self.view.lbl_cover.setText("正在加载海报...")
                    proxies = self.get_active_proxies()
                    
                    worker = ImageLoadWorker(filepath, cover_url, proxies, self.image_session, is_poster=True)
                    worker.signals.loaded.connect(self.on_network_image_loaded)
                    worker.signals.finished_worker.connect(self.on_worker_destroyed)

                    self.active_workers.add(worker)
                    self.thread_pool.start(worker)
                    poster_loaded = True
            
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
            tmpl = self.view.tmpl_input.text().strip()
            local_folder = format_target_path(tmpl, output_dir, code, detail)
            local_extrafanart_dir = os.path.join(local_folder, "extrafanart")
            
            if os.path.exists(local_extrafanart_dir):
                for file_name in sorted(os.listdir(local_extrafanart_dir)):
                    if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                        full_img_path = os.path.join(local_extrafanart_dir, file_name)
                        
                        cache_key = (full_img_path, 90)
                        lbl = ClickableLabel()
                        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                        
                        if cache_key in self.pixmap_cache:
                            lbl.setPixmap(self.pixmap_cache[cache_key])
                            lbl.pixmap_data = QPixmap(full_img_path)
                        else:
                            pix = QPixmap(full_img_path)
                            if not pix.isNull():
                                scaled_pix = pix.scaledToHeight(90, Qt.TransformationMode.SmoothTransformation)
                                self.pixmap_cache[cache_key] = scaled_pix
                                lbl.setPixmap(scaled_pix)
                                lbl.pixmap_data = pix
                        
                        lbl.clicked.connect(self.show_zoomed_image)
                        self.view.samples_layout.addWidget(lbl)
        else:
            thumbnails = detail.get("thumbnail_images", [])
            if thumbnails:
                proxies = self.get_active_proxies()
                urls_to_load = thumbnails[1:] if len(thumbnails) > 1 else thumbnails
                for url in urls_to_load:
                    cache_key = (url, 90)
                    if cache_key in self.pixmap_cache:
                        lbl = ClickableLabel()
                        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                        lbl.setPixmap(self.pixmap_cache[cache_key])
                        
                        raw_key = (url, "raw")
                        if raw_key in self.pixmap_cache:
                            lbl.pixmap_data = self.pixmap_cache[raw_key]
                        else:
                            lbl.pixmap_data = self.pixmap_cache[cache_key]
                            
                        lbl.clicked.connect(self.show_zoomed_image)
                        self.view.samples_layout.addWidget(lbl)
                    else:
                        worker = ImageLoadWorker(filepath, url, proxies, self.image_session, is_poster=False)
                        worker.signals.loaded.connect(self.on_network_image_loaded)
                        worker.signals.finished_worker.connect(self.on_worker_destroyed)

                        self.active_workers.add(worker)
                        self.thread_pool.start(worker)

    def on_network_image_loaded(self, filepath, url, data, is_poster):
        if self.current_preview_filepath == filepath:
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                if is_poster:
                    w, h = self.view.lbl_cover.width(), self.view.lbl_cover.height()
                    scaled_pix = pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.pixmap_cache[(url, w, h)] = scaled_pix
                    self.view.lbl_cover.setPixmap(scaled_pix)
                else:
                    h_target = 90
                    cache_key = (url, h_target)
                    raw_key = (url, "raw")
                    
                    self.pixmap_cache[raw_key] = pix
                    scaled_pix = pix.scaledToHeight(h_target, Qt.TransformationMode.SmoothTransformation)
                    self.pixmap_cache[cache_key] = scaled_pix
                    
                    lbl = ClickableLabel()
                    lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                    lbl.setPixmap(scaled_pix)
                    lbl.pixmap_data = pix
                    lbl.clicked.connect(self.show_zoomed_image)
                    self.view.samples_layout.addWidget(lbl)

    def show_zoomed_image(self, clicked_label):
        pixmaps = []
        current_index = 0
        if hasattr(self.view, "samples_layout"):
            for i in range(self.view.samples_layout.count()):
                widget = self.view.samples_layout.itemAt(i).widget()
                if isinstance(widget, ClickableLabel) and widget.pixmap_data:
                    pixmaps.append(widget.pixmap_data)
                    if widget == clicked_label:
                        current_index = len(pixmaps) - 1

        if pixmaps:
            dialog = PhotoDialog(pixmaps, current_index, self.view)
            dialog.exec()

    def reset_preview_panel(self):
        self.view.lbl_cover.setText("选择影片以预览海报")
        self.view.lbl_cover.setPixmap(QPixmap())
        self.view.lbl_info_title.setText(
            "<div style='margin-top: 10px; color: #8E8E93; font-size: 13px; font-weight: bold;'>影片番号与标题</div>"
        )
        self.view.lbl_info_details.setText("制片商: -\n发行日期: -\n演员: -")
        self.view.table_magnet.setRowCount(0)
        
        if hasattr(self.view, "samples_layout"):
            while self.view.samples_layout.count():
                item = self.view.samples_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def _parse_size_mb(self, size_str) -> float:
        if not size_str:
            return 0.0
        import re
        s = size_str.upper().strip()
        match = re.match(r'^([\d\.]+)\s*(GB|MB|KB|B|G|M|K)?', s)
        if not match:
            return 0.0
        num = float(match.group(1))
        unit = match.group(2)
        if unit in ('GB', 'G'):
            return num * 1024.0
        elif unit in ('MB', 'M'):
            return num
        elif unit in ('KB', 'K'):
            return num / 1024.0
        elif unit == 'B':
            return num / (1024.0 * 1024.0)
        return num

    def test_proxy_connection(self):
        proxy = self.view.proxy_input.text().strip()
        self.view.lbl_proxy_status.setText("正在测试连接...")
        self.view.lbl_proxy_status.setStyleSheet("color: #E5C158;")
        self.view.btn_test_proxy.setEnabled(False)

        worker = ProxyTestWorker(proxy)

        def on_test_finished(success, msg):
            self.view.lbl_proxy_status.setText(msg)
            if success:
                self.view.lbl_proxy_status.setStyleSheet("color: #34C759;")
            else:
                self.view.lbl_proxy_status.setStyleSheet("color: #FF453A;")
            self.view.btn_test_proxy.setEnabled(True)

        worker.signals.finished.connect(on_test_finished)
        self.thread_pool.start(worker)

    def load_cookie_config(self):
        cookie_path = config.COOKIE_FILE
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_data.items()])
                    self.view.cookie_input.setText(cookie_str)
            except:
                pass

    def save_cookie_config(self):
        cookie_str = self.view.cookie_input.text().strip()
        if not cookie_str:
            QMessageBox.information(self.view, "提示", "Cookie 为空")
            return
            
        cookies_dict = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                cookies_dict[k.strip()] = v.strip()

        cookie_path = config.COOKIE_FILE
        try:
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, indent=2)
            QMessageBox.information(self.view, "成功", "Cookie 已成功保存至本地 cookies.json")
        except Exception as e:
            QMessageBox.critical(self.view, "错误", f"Cookie 保存失败: {e}")

    def auto_save_cookie_config(self):
        cookie_str = self.view.cookie_input.text().strip()
        cookies_dict = {}
        if cookie_str:
            for item in cookie_str.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies_dict[k.strip()] = v.strip()
        
        cookie_path = config.COOKIE_FILE
        try:
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, indent=2)
        except Exception as e:
            print(f"自动保存 Cookie 失败: {e}")

    def retry_failed_tasks(self):
        failed_count = 0
        for fp, info in self.task_files.items():
            status = info.get("status", "")
            if "失败" in status or "异常" in status or status.startswith("❌"):
                info["status"] = "等待中"
                row = info["row"]
                status_item = self.view.table.item(row, 3)
                if status_item:
                    status_item.setText("等待中")
                failed_count += 1
                
        if failed_count == 0:
            QMessageBox.information(self.view, "提示", "列表中没有失败的任务需要重试")
            return
            
        self.save_backup()
        self.start_scraping()
        self.apply_task_filter()

    def copy_to_clipboard(self, text):
        if text:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self.view, "提示", "磁力链接已成功复制到剪贴板！")
