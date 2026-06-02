import os
import json
import requests
from PySide6.QtCore import QThreadPool, Qt, Signal, QRunnable, QObject
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QProgressBar, QWidget, QMenu
from PySide6.QtGui import QPixmap
from gui.main_window import MainWindow
from gui.scrape_worker import ScrapeWorker
from lib.code_extractor import extract_code
from gui.folder_cleaner import clean_empty_parent_dirs
from gui.task_persister import (
    save_tasks_backup, load_tasks_backup,
    save_settings_backup, load_settings_backup
)

class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            v1 = self.sort_value
            v2 = other.sort_value
            if v1 is None:
                return True
            if v2 is None:
                return False
            return v1 < v2
        return super().__lt__(other)

class PhotoDialog(QDialog):
    def __init__(self, pixmaps, current_index, parent=None):
        super().__init__(parent)
        self.pixmaps = pixmaps
        self.current_index = current_index
        self.setWindowTitle("剧照放大预览")
        
        # 窗口物理尺寸固定，大图横竖切换时窗口不跳动，视觉更平滑稳定
        self.setFixedSize(920, 650)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        # 中间大图容器：[左按钮] [大图显示] [右按钮]
        middle_layout = QHBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(15)
        
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setObjectName("PrevPhotoBtn")
        self.btn_prev.clicked.connect(self.show_prev)
        
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setFixedSize(800, 600)
        
        self.btn_next = QPushButton("▶")
        self.btn_next.setObjectName("NextPhotoBtn")
        self.btn_next.clicked.connect(self.show_next)
        
        middle_layout.addWidget(self.btn_prev)
        middle_layout.addWidget(self.lbl_image)
        middle_layout.addWidget(self.btn_next)
        main_layout.addLayout(middle_layout)
        
        # 底部页码
        self.lbl_info = QLabel()
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setStyleSheet("color: #FF5924; font-weight: bold; font-size: 12px; margin-top: 2px;")
        main_layout.addWidget(self.lbl_info)
        
        # 渲染当前图片
        self.update_view()
        
        # 样式美化（只作用于看图窗口内，不污染外部）
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1.5px solid #E5EAF2;
                border-radius: 16px;
            }
            QPushButton#PrevPhotoBtn, QPushButton#NextPhotoBtn {
                background-color: rgba(255, 255, 255, 0.8);
                border: 1px solid #E5EAF2;
                border-radius: 20px;
                min-width: 40px;
                min-height: 40px;
                max-width: 40px;
                max-height: 40px;
                font-size: 16px;
                color: #4A5465;
                font-weight: bold;
            }
            QPushButton#PrevPhotoBtn:hover, QPushButton#NextPhotoBtn:hover {
                background-color: rgba(255, 89, 36, 0.08);
                border-color: #FF5924;
                color: #FF5924;
            }
            QPushButton#PrevPhotoBtn:disabled, QPushButton#NextPhotoBtn:disabled {
                background-color: rgba(240, 242, 245, 0.3);
                border-color: #E5EAF2;
                color: #C0C4CC;
            }
        """)

    def update_view(self):
        if not self.pixmaps or self.current_index < 0 or self.current_index >= len(self.pixmaps):
            return
            
        pixmap = self.pixmaps[self.current_index]
        scaled = pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_image.setPixmap(scaled)
        
        # 页码指示
        self.lbl_info.setText(f"剧照预览：{self.current_index + 1} / {len(self.pixmaps)}")
        
        # 按钮置灰状态设置
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.pixmaps) - 1)

    def show_prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_view()

    def show_next(self):
        if self.current_index < len(self.pixmaps) - 1:
            self.current_index += 1
            self.update_view()

    def keyPressEvent(self, event):
        # 键盘左右键切换
        if event.key() == Qt.Key.Key_Left:
            self.show_prev()
        elif event.key() == Qt.Key.Key_Right:
            self.show_next()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # 点击中间大图区域则自动关闭弹窗
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.lbl_image.geometry().contains(pos):
                self.accept()

class ClickableLabel(QLabel):
    clicked = Signal(QLabel)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap_data = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.pixmap_data:
                self.clicked.emit(self)

class ImageLoadSignals(QObject):
    loaded = Signal(str, str, bytes, bool)  # filepath, url, content, is_poster
    finished_worker = Signal(object)  # worker object

class ImageLoadWorker(QRunnable):
    def __init__(self, filepath, url, proxies=None, session=None, is_poster=False):
        super().__init__()
        self.filepath = filepath
        self.url = url
        self.proxies = proxies
        self.session = session
        self.is_poster = is_poster
        self.signals = ImageLoadSignals()

    def run(self):
        try:
            try:
                caller = self.session if self.session else requests
                r = caller.get(self.url, timeout=10, proxies=self.proxies)
                if r.status_code == 200:
                    self.signals.loaded.emit(self.filepath, self.url, r.content, self.is_poster)
            except Exception as e:
                pass
        finally:
            self.signals.finished_worker.emit(self)

class Controller:
    def __init__(self, view: MainWindow):
        self.view = view
        self.thread_pool = QThreadPool.globalInstance()
        
        # 专用的刮削线程池，限制并发为 3，防止被平台封锁 IP
        self.scrape_pool = QThreadPool()
        self.scrape_pool.setMaxThreadCount(3)
        
        # 存储所有正在排队或执行的任务文件：{file_path: {"code": str, "row": int, "detail": dict, "status": str}}
        self.task_files = {}
        self.current_preview_filepath = None
        self.processed_parent_dirs = set()
        self.active_workers = set()
        self.image_session = requests.Session()
        self.pixmap_cache = {}  # 缩放好的 QPixmap 强引用内存缓存系统：(path_or_url, w, h) -> QPixmap

        # 默认保存路径为项目根目录下的 output 文件夹
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
        self.view.path_input.setText(default_out)

        # 信号槽绑定
        self.view.files_dropped.connect(self.handle_files_dropped)
        self.view.btn_browse.clicked.connect(self.browse_output_dir)
        self.view.btn_clear.clicked.connect(self.clear_all_tasks)
        self.view.drop_label.clicked.connect(lambda: self.import_files_manually())
        self.view.btn_import_dir.clicked.connect(lambda: self.import_dir_manually())
        self.view.btn_add_code.clicked.connect(lambda: self.add_code_manually())
        self.view.btn_start.clicked.connect(self.start_scraping)
        self.view.btn_organize.clicked.connect(self.start_organizing)
        self.view.btn_test_proxy.clicked.connect(self.test_proxy_connection)
        self.view.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.view.table.itemChanged.connect(self.handle_cell_changed)
        self.view.btn_save_cookie.clicked.connect(self.save_cookie_config)
        self.view.btn_remove_selected.clicked.connect(self.remove_selected_task)
        self.view.btn_retry_failed.clicked.connect(self.retry_failed_tasks)
        self.view.table.delete_pressed.connect(self.remove_selected_task)
        
        # 开启表格右键上下文菜单
        self.view.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.table.customContextMenuRequested.connect(self.show_table_context_menu)

        # 自动加载已有的 Cookie 进行显示
        self.load_cookie_config()
        self.view.cookie_input.textChanged.connect(self.auto_save_cookie_config)

        # 加载本地历史配置设置
        self.load_settings()

        # 从本地备份中还原历史刮削任务
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
        
        # 按照 row 升序恢复
        sorted_tasks = sorted(restored.items(), key=lambda x: x[1].get("row", 0))
        
        for idx, (filepath, info) in enumerate(sorted_tasks):
            row = self.view.table.rowCount()
            self.view.table.insertRow(row)

            # 更新 row
            info["row"] = row

            # ID 列
            id_item = QTableWidgetItem(f"{row + 1:02d}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 0, id_item)

            # 原文件名
            if filepath.startswith("__virtual__"):
                name_text = "[无本地视频: 仅刮削元数据]"
            else:
                name_text = os.path.basename(filepath)
            name_item = QTableWidgetItem(name_text)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 1, name_item)

            # 番号
            code_item = QTableWidgetItem(info.get("code", ""))
            self.view.table.setItem(row, 2, code_item)

            # 状态
            status_text = info.get("status", "等待中")
            if status_text in ("开始执行", "准备中") or status_text.startswith("正在"):
                status_text = "等待中"
                info["status"] = "等待中"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)

            self.task_files[filepath] = info

        # 选中第一行
        if self.view.table.rowCount() > 0:
            self.view.table.selectRow(0)

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

        added_files = []
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
            status_text = "正在刮削..." if code else "番号待补充"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)

            self.task_files[file_path] = {
                "code": code,
                "row": row,
                "detail": None,
                "status": status_text
            }
            if code:
                added_files.append(file_path)

        # 如果有新加入并且包含识别番号的文件，自动触发多线程刮削，并选中第一个以显示进度
        if added_files:
            # 自动选中第一个新加任务，右侧激活联动预览
            first_info = self.task_files[added_files[0]]
            self.view.table.selectRow(first_info["row"])

            output_dir = self.view.path_input.text().strip()
            if output_dir:
                proxies = None
                if self.view.chk_custom_proxy.isChecked():
                    proxy = self.view.proxy_input.text().strip()
                    proxies = {"http": proxy, "https": proxy} if proxy else None
                platform = "javdb"

                for fp in added_files:
                    worker = ScrapeWorker(fp, self.task_files[fp]["code"], output_dir, platform, proxies, only_scrape=True)
                    worker.setAutoDelete(False)
                    worker.signals.started.connect(self.on_worker_started)
                    worker.signals.progress.connect(self.on_worker_progress)
                    worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
                    worker.signals.finished.connect(self.on_worker_finished)
                    worker.signals.finished_worker.connect(self.on_worker_destroyed)

                    self.active_workers.add(worker)
                    self.scrape_pool.start(worker)

        self.save_backup()
        self.view.update_empty_placeholder_visibility(len(self.task_files) == 0)

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
            status_item = QTableWidgetItem("正在刮削...")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table.setItem(row, 3, status_item)
            
            self.task_files[virtual_path] = {
                "code": code,
                "row": row,
                "detail": None,
                "status": "正在刮削..."
            }

            # 自动选中刚添加的任务行，激活右侧面板预览
            self.view.table.selectRow(row)

            # 自动开始刮削，免除二次点击
            output_dir = self.view.path_input.text().strip()
            if output_dir:
                proxies = None
                if self.view.chk_custom_proxy.isChecked():
                    proxy = self.view.proxy_input.text().strip()
                    proxies = {"http": proxy, "https": proxy} if proxy else None
                platform = "javdb"

                worker = ScrapeWorker(virtual_path, code, output_dir, platform, proxies, only_scrape=True)
                worker.setAutoDelete(False)
                worker.signals.started.connect(self.on_worker_started)
                worker.signals.progress.connect(self.on_worker_progress)
                worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
                worker.signals.finished.connect(self.on_worker_finished)
                worker.signals.finished_worker.connect(self.on_worker_destroyed)

                self.active_workers.add(worker)
                self.scrape_pool.start(worker)
            self.save_backup()
            self.view.update_empty_placeholder_visibility(len(self.task_files) == 0)

    def handle_cell_changed(self, item):
        # 当用户在表格中双击编辑修改番号时触发
        if item.column() == 2:
            row = item.row()
            target_fp = None
            new_code = None
            for fp, info in self.task_files.items():
                if info["row"] == row:
                    new_code = item.text().strip().upper()
                    # 暂时屏蔽信号，防止由于 setText 大写转化引发递归重入
                    self.view.table.blockSignals(True)
                    item.setText(new_code)
                    self.view.table.blockSignals(False)
                    info["code"] = new_code
                    target_fp = fp
                    break
            
            if target_fp and new_code:
                # 1. 更新状态为 正在刮削...
                info = self.task_files[target_fp]
                info["status"] = "正在刮削..."
                
                status_item = self.view.table.item(row, 3)
                if status_item:
                    status_item.setText("正在刮削...")
                
                self.save_backup()
                
                # 2. 自动拉起 ScrapeWorker 异步进行刮削
                output_dir = self.view.path_input.text().strip()
                if output_dir:
                    proxies = None
                    if self.view.chk_custom_proxy.isChecked():
                        proxy = self.view.proxy_input.text().strip()
                        proxies = {"http": proxy, "https": proxy} if proxy else None
                    platform = "javdb"

                    worker = ScrapeWorker(target_fp, new_code, output_dir, platform, proxies, only_scrape=True)
                    worker.setAutoDelete(False)
                    worker.signals.started.connect(self.on_worker_started)
                    worker.signals.progress.connect(self.on_worker_progress)
                    worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
                    worker.signals.finished.connect(self.on_worker_finished)
                    worker.signals.finished_worker.connect(self.on_worker_destroyed)

                    self.active_workers.add(worker)
                    self.scrape_pool.start(worker)
            elif target_fp:
                # 若番号被清空
                info = self.task_files[target_fp]
                info["status"] = "番号待补充"
                status_item = self.view.table.item(row, 3)
                if status_item:
                    status_item.setText("番号待补充")
                self.save_backup()

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self.view, "选择保存目标文件夹")
        if dir_path:
            abs_path = os.path.abspath(dir_path)
            self.view.path_input.setText(abs_path)
            self.save_settings(abs_path)

    def save_settings(self, output_dir: str):
        settings = load_settings_backup()
        settings["output_dir"] = output_dir
        save_settings_backup(settings)

    def load_settings(self):
        settings = load_settings_backup()
        output_dir = settings.get("output_dir", "")
        if output_dir:
            self.view.path_input.setText(output_dir)

    def clear_all_tasks(self):
        self.view.table.setRowCount(0)
        self.task_files.clear()
        self.pixmap_cache.clear()  # 清空图片缓存，释放内存
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
        reset_preview = False
        
        for row in sorted_rows:
            target_fp = None
            for fp, info in self.task_files.items():
                if info["row"] == row:
                    target_fp = fp
                    break
            
            if target_fp:
                if self.current_preview_filepath == target_fp:
                    reset_preview = True
                # 1. 从数据字典中删除
                if target_fp in self.task_files:
                    del self.task_files[target_fp]
                
                # 2. 从 QTableWidget 中移除该行
                self.view.table.removeRow(row)
                
                # 3. 更新剩余所有任务的 row 索引
                for fp, info in self.task_files.items():
                    if info["row"] > row:
                        info["row"] -= 1

        # 4. 更新 ID 列，使其连续
        for r in range(self.view.table.rowCount()):
            id_item = self.view.table.item(r, 0)
            if id_item:
                id_item.setText(f"{r + 1:02d}")
                
        # 5. 如果删除了当前选中的预览任务，重置右侧预览
        if reset_preview:
            self.reset_preview_panel()
            
        self.save_backup()
        self.view.update_empty_placeholder_visibility(len(self.task_files) == 0)

    def show_table_context_menu(self, pos):
        # 获取右键点击的单元格对应的行
        item = self.view.table.itemAt(pos)
        if not item:
            return
            
        row = item.row()
        
        # 收集目前所有被选中的行
        selected_rows = set()
        for range_obj in self.view.table.selectedRanges():
            for r in range(range_obj.topRow(), range_obj.bottomRow() + 1):
                selected_rows.add(r)
                
        # 如果右键点击的这一行没有被包含在已选中的行中，我们把它单独选中
        if row not in selected_rows:
            self.view.table.selectRow(row)
            selected_rows = {row}
            
        # 根据选中的行号，找到对应的所有文件路径
        selected_fps = []
        for r in selected_rows:
            for fp, info in self.task_files.items():
                if info["row"] == r:
                    selected_fps.append(fp)
                    break
                    
        if not selected_fps:
            return
            
        count = len(selected_fps)
        
        # 创建右键菜单
        menu = QMenu(self.view)
        
        # 美化右键菜单样式（符合 Meadow 轻奢白金主题，白底、细边框、悬浮橙红高亮）
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
        
        if count > 1:
            action_scrape = menu.addAction(f"仅刮削选中的影片 ({count}部)")
            action_organize = menu.addAction(f"仅整理选中的影片 ({count}部)")
            menu.addSeparator()
            action_remove = menu.addAction(f"从列表中移除选中的影片 ({count}部)")
        else:
            action_scrape = menu.addAction("仅刮削此影片")
            action_organize = menu.addAction("仅整理此影片")
            menu.addSeparator()
            action_remove = menu.addAction("从列表中移除")
            
        # 只要选中的影片中有至少一个是有番号的，且不是在执行中，就可用
        any_has_code = any(self.task_files[fp]["code"] for fp in selected_fps)
        any_running = any(self.task_files[fp]["status"] in ["正在刮削...", "整理中..."] for fp in selected_fps)
        
        if not any_has_code:
            action_scrape.setEnabled(False)
            action_organize.setEnabled(False)
        if any_running:
            action_scrape.setEnabled(False)
            action_organize.setEnabled(False)
            
        # 弹出菜单并阻塞等待选择
        global_pos = self.view.table.viewport().mapToGlobal(pos)
        selected_action = menu.exec(global_pos)
        
        if selected_action == action_scrape:
            self.scrape_multiple_tasks(selected_fps)
        elif selected_action == action_organize:
            self.organize_multiple_tasks(selected_fps)
        elif selected_action == action_remove:
            self.remove_selected_task()

    def scrape_multiple_tasks(self, file_paths):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return
            
        proxies = None
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb"
        
        for fp in file_paths:
            info = self.task_files.get(fp)
            if not info or not info["code"]:
                continue
            if info["status"] in ["正在刮削...", "整理中..."]:
                continue
                
            code = info["code"]
            info["status"] = "正在刮削..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("正在刮削..."))
            
            worker = ScrapeWorker(fp, code, output_dir, platform, proxies, only_scrape=True)
            worker.setAutoDelete(False)
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)
            worker.signals.finished_worker.connect(self.on_worker_destroyed)
            
            self.active_workers.add(worker)
            self.scrape_pool.start(worker)
        self.save_backup()

    def organize_multiple_tasks(self, file_paths):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return
            
        proxies = None
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb"
        
        for fp in file_paths:
            info = self.task_files.get(fp)
            if not info or not info["code"]:
                continue
            if info["status"] == "整理中...":
                continue
                
            code = info["code"]
            info["status"] = "整理中..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("整理中..."))
            
            worker = ScrapeWorker(fp, code, output_dir, platform, proxies, only_scrape=False, cached_detail=info["detail"])
            worker.setAutoDelete(False)
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)
            worker.signals.finished_worker.connect(self.on_worker_destroyed)
            
            self.active_workers.add(worker)
            self.scrape_pool.start(worker)
        self.save_backup()

    def reset_preview_panel(self):
        self.view.lbl_cover.setText("选择影片以预览海报")
        self.view.lbl_cover.setPixmap(QPixmap())
        self.view.lbl_info_title.setText(
            "<div style='margin-top: 10px; color: #8E8E93; font-size: 13px; font-weight: bold;'>影片番号与标题</div>"
        )
        self.view.lbl_info_details.setText("制片商: -\n发行日期: -\n演员: -")
        self.view.table_magnet.setRowCount(0)
        
        # 清空剧照 samples_layout
        if hasattr(self.view, "samples_layout"):
            while self.view.samples_layout.count():
                item = self.view.samples_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def get_local_target_folder(self, output_dir, code, detail):
        """
        统一计算整理后，包含演员专属子目录的最终保存目录路径。
        """
        actors = detail.get("actors", [])
        actor_name = actors[0].strip() if actors else "未知演员"
        for char in r'\/:*?"<>|':
            actor_name = actor_name.replace(char, " ")
        actor_name = actor_name.strip() or "未知演员"
        
        clean_title = detail.get("title", "")
        for char in r'\/:*?"<>|':
            clean_title = clean_title.replace(char, " ")
        folder_name = f"[{code}] {clean_title}"[:120].strip()
        
        return os.path.join(output_dir, actor_name, folder_name)

    def _parse_size_mb(self, size_str):
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

    def auto_save_cookie_config(self):
        import config
        import json
        cookie_str = self.view.cookie_input.toPlainText().strip()
        cookies_dict = {}
        if cookie_str:
            for item in cookie_str.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies_dict[k.strip()] = v.strip()
        
        cookie_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", config.COOKIE_FILE))
        try:
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, indent=2)
        except Exception as e:
            print(f"自动保存 Cookie 失败: {e}")

    def retry_failed_tasks(self):
        failed_count = 0
        for fp, info in self.task_files.items():
            status = info.get("status", "")
            if "失败" in status:
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

    def start_scraping(self):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return

        # 统计任务文件
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
            QMessageBox.information(self.view, "提示", "列表中没有可以刮削的影片番号")
            return

        # 如果没有新任务但有已刮削任务，询问是否重新刮削
        if not todo_files and done_files:
            reply = QMessageBox.question(
                self.view, "重新刮削提示",
                "所选影片均已刮削过，是否要重新刮削？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                todo_files = done_files
            else:
                return

        proxies = None
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb"

        for file_path in todo_files:
            info = self.task_files[file_path]
            code = info["code"]
            info["status"] = "正在刮削..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("正在刮削..."))

            # 仅执行刮削预览
            worker = ScrapeWorker(file_path, code, output_dir, platform, proxies, only_scrape=True)
            worker.setAutoDelete(False)
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)
            worker.signals.finished_worker.connect(self.on_worker_destroyed)

            self.active_workers.add(worker)
            self.scrape_pool.start(worker)
        self.save_backup()

    def start_organizing(self):
        output_dir = self.view.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
            return

        # 统计任务文件
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
            QMessageBox.information(self.view, "提示", "列表中没有有效的整理落盘任务")
            return

        # 如果没有未整理任务，但有已整理成功任务，询问是否重新整理
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

        proxies = None
        if self.view.chk_custom_proxy.isChecked():
            proxy = self.view.proxy_input.text().strip()
            proxies = {"http": proxy, "https": proxy} if proxy else None
        platform = "javdb"

        for file_path in todo_files:
            info = self.task_files[file_path]
            code = info["code"]
            info["status"] = "整理中..."
            row = info["row"]
            self.view.table.setItem(row, 3, QTableWidgetItem("整理中..."))

            # 执行整理落盘。如果已经缓存有元数据，直接传入 detail 免去重复请求
            worker = ScrapeWorker(file_path, code, output_dir, platform, proxies, only_scrape=False, cached_detail=info["detail"])
            worker.setAutoDelete(False)
            worker.signals.started.connect(self.on_worker_started)
            worker.signals.progress.connect(self.on_worker_progress)
            worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
            worker.signals.finished.connect(self.on_worker_finished)
            worker.signals.finished_worker.connect(self.on_worker_destroyed)

            self.active_workers.add(worker)
            self.scrape_pool.start(worker)
        self.save_backup()

    # ================== 后台线程信号槽 ==================
    def on_worker_destroyed(self, worker):
        self.active_workers.discard(worker)

    def on_worker_started(self, filepath):
        if filepath in self.task_files:
            info = self.task_files[filepath]
            info["status"] = "开始执行"
            self.view.table.removeCellWidget(info["row"], 3)
            self.view.table.setItem(info["row"], 3, QTableWidgetItem("开始执行"))
            self.save_backup()

    def on_worker_progress(self, filepath, message):
        if filepath in self.task_files:
            info = self.task_files[filepath]
            info["status"] = message
            row = info["row"]
            
            import re
            match = re.search(r"\((\d+)/(\d+)\)", message)
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

    def on_worker_preview_loaded(self, filepath, detail):
        # 缓存抓取到的元数据
        if filepath in self.task_files:
            self.task_files[filepath]["detail"] = detail
            
        self.save_backup()

        # 如果当前选中了这一行，则立即刷新右侧预览
        selected_ranges = self.view.table.selectedRanges()
        if selected_ranges:
            current_row = selected_ranges[0].topRow()
            if filepath in self.task_files and self.task_files[filepath]["row"] == current_row:
                self.show_preview_details(detail, filepath)

    def on_worker_finished(self, filepath, status):
        if filepath in self.task_files:
            info = self.task_files[filepath]
            self.view.table.removeCellWidget(info["row"], 3)
            if status == "success":
                info["status"] = "已整理成功"
                self.view.table.setItem(info["row"], 3, QTableWidgetItem("✅ 已整理成功"))
                
                # 如果成功，且当前选中该行，加载本地已下载的海报和剧照展示
                selected_ranges = self.view.table.selectedRanges()
                if selected_ranges and selected_ranges[0].topRow() == info["row"]:
                    detail = info["detail"]
                    self.show_preview_details(detail, filepath, loaded_local=True)
                
                # 记录发生移动的源文件父目录
                if not filepath.startswith("__virtual__:"):
                    parent_dir = os.path.dirname(filepath)
                    self.processed_parent_dirs.add(parent_dir)
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
                self.view.table.setItem(info["row"], 3, QTableWidgetItem(f"❌ 失败: {status}"))
            
            self.save_backup()

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
                            QMessageBox.warning(self.view, "删除失败", f"无法删除文件夹: {pdir}\n错误: {e}")
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
            # 判断是否已经刮削成功并下载好本地图片
            is_success = info["status"] == "已整理成功"
            self.show_preview_details(detail, filepath, loaded_local=is_success)
        else:
            # 未刮削或刮削中，仅显示基础文件名信息
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

        # 整理详情文本
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
                target_folder = self.get_local_target_folder(output_dir, code, detail)
                info_details_text += f"整理后路径: {target_folder}\n\n"
            else:
                info_details_text += f"原文件路径: {filepath}\n\n"
            
        info_details_text += f"标签: {', '.join(detail.get('tags', []))}"
        self.view.lbl_info_details.setText(info_details_text)

        # 渲染磁力链接表格
        self.view.table_magnet.setSortingEnabled(False)
        self.view.table_magnet.setRowCount(0)
        
        magnets = detail.get("magnets", [])
        import re
        for mag in magnets:
            row = self.view.table_magnet.rowCount()
            self.view.table_magnet.insertRow(row)

            # 获取磁力链接
            magnet_link = mag.get("magnet") or mag.get("link") or ""

            # 判断是 JAVDB 还是 JAVBUS
            if "magnet" in mag:  # JAVDB
                size_text = mag.get("size_text") or "未知大小"
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', size_text)
                if date_match:
                    date_str = date_match.group(0)
                    size_str = size_text.replace(date_str, "").strip(", ")
                else:
                    date_str = "-"
                    size_str = size_text
                size_mb = mag.get("size_mb") or self._parse_size_mb(size_str)
            else:  # JAVBUS
                size_str = mag.get("size") or "未知大小"
                date_str = mag.get("share_date") or "-"
                size_mb = self._parse_size_mb(size_str)

            # 大小列
            size_item = SortableTableWidgetItem(size_str, size_mb)
            size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.view.table_magnet.setItem(row, 0, size_item)

            # 日期列
            date_item = SortableTableWidgetItem(date_str, date_str)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.view.table_magnet.setItem(row, 1, date_item)

            # 复制操作按钮 (第2列)
            btn_copy = QPushButton("复制")
            btn_copy.setObjectName("CopyMagnetBtn")
            btn_copy.setStyleSheet("""
                QPushButton {
                    background-color: #FF5924;
                    color: #FFFFFF;
                    border: 1px solid #FF5924;
                    border-radius: 10px;
                    padding: 2px 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FF8550;
                    border-color: #FF8550;
                }
                QPushButton:pressed {
                    background-color: #E04414;
                    border-color: #E04414;
                }
            """)
            btn_copy.clicked.connect(lambda checked=False, link=magnet_link: self.copy_to_clipboard(link))
            self.view.table_magnet.setCellWidget(row, 2, btn_copy)

            # 按钮列需要占位，以防排序导致单元格状态混乱
            dummy_item = SortableTableWidgetItem("", "")
            dummy_item.setFlags(dummy_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.view.table_magnet.setItem(row, 2, dummy_item)

        # 默认按大小列(第0列)降序排列
        self.view.table_magnet.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.view.table_magnet.setSortingEnabled(True)

        # 渲染海报图片
        poster_loaded = False
        w, h = self.view.lbl_cover.width(), self.view.lbl_cover.height()

        if loaded_local:
            output_dir = self.view.path_input.text().strip()
            local_poster_path = os.path.join(self.get_local_target_folder(output_dir, code, detail), "poster.jpg")
            
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
            # 刮削中/未完成时直接使用网络地址预览海报
            cover_url = detail.get("cover_url")
            if cover_url:
                cache_key = (cover_url, w, h)
                if cache_key in self.pixmap_cache:
                    self.view.lbl_cover.setPixmap(self.pixmap_cache[cache_key])
                    poster_loaded = True
                else:
                    self.view.lbl_cover.setText("正在加载海报...")
                    proxies = None
                    if self.view.chk_custom_proxy.isChecked():
                        proxy = self.view.proxy_input.text().strip()
                        proxies = {"http": proxy, "https": proxy} if proxy else None
                    
                    worker = ImageLoadWorker(filepath, cover_url, proxies, self.image_session, is_poster=True)
                    worker.setAutoDelete(False)
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
            local_folder = self.get_local_target_folder(output_dir, code, detail)
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
                        worker.setAutoDelete(False)
                        worker.signals.loaded.connect(self.on_network_image_loaded)
                        worker.signals.finished_worker.connect(self.on_worker_destroyed)

                        self.active_workers.add(worker)
                        self.thread_pool.start(worker)

    def on_network_image_loaded(self, filepath, url, data, is_poster):
        # 确保只有当前正在预览的视频才显示，防错乱
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

    def copy_to_clipboard(self, text):
        if text:
            from PySide6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self.view, "提示", "磁力链接已成功复制到剪贴板！")
