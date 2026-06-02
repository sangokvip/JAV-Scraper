import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit, QTextEdit,
    QFileDialog, QAbstractItemView, QHeaderView, QRadioButton, QButtonGroup,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap

class TaskTableWidget(QTableWidget):
    delete_pressed = Signal()
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_pressed.emit()
        else:
            super().keyPressEvent(event)

class ClickableDropLabel(QLabel):
    clicked = Signal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class MainWindow(QMainWindow):
    files_dropped = Signal(list)  # 拖入的文件路径列表

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JAV SCRAPER")
        self.resize(1150, 720)
        self.init_ui()
        self.apply_stylesheet()

    def init_ui(self):
        # 主中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ================== 左侧：配置区 ==================
        left_panel = QWidget()
        left_panel.setObjectName("LeftPanel")
        left_panel.setFixedWidth(260)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        # 首选源
        left_layout.addWidget(QLabel("首选刮削源:"))
        self.source_group = QButtonGroup(self)
        self.radio_javdb = QRadioButton("JAVDB")
        self.radio_javdb.setChecked(True)
        self.radio_javbus = QRadioButton("JAVBUS")
        self.source_group.addButton(self.radio_javdb)
        self.source_group.addButton(self.radio_javbus)
        source_layout = QHBoxLayout()
        source_layout.addWidget(self.radio_javdb)
        source_layout.addWidget(self.radio_javbus)
        left_layout.addLayout(source_layout)

        # 代理设置
        left_layout.addWidget(QLabel("代理设置 (SOCKS5/HTTP):"))
        self.chk_custom_proxy = QCheckBox("启用自定义代理")
        self.chk_custom_proxy.setObjectName("CustomProxyCheck")
        self.chk_custom_proxy.setChecked(False)
        left_layout.addWidget(self.chk_custom_proxy)

        self.proxy_input = QLineEdit("http://127.0.0.1:10808")
        self.proxy_input.setPlaceholderText("例如 http://127.0.0.1:10808")
        self.proxy_input.setEnabled(False)
        left_layout.addWidget(self.proxy_input)

        self.btn_test_proxy = QPushButton("测试代理连接")
        self.btn_test_proxy.setEnabled(False)
        left_layout.addWidget(self.btn_test_proxy)

        # 信号联动绑定
        self.chk_custom_proxy.toggled.connect(self.proxy_input.setEnabled)
        self.chk_custom_proxy.toggled.connect(self.btn_test_proxy.setEnabled)

        self.lbl_proxy_status = QLabel("代理状态: 系统代理模式")
        self.lbl_proxy_status.setObjectName("ProxyStatusLabel")
        left_layout.addWidget(self.lbl_proxy_status)

        # 联动更新提示状态 and 颜色
        def update_proxy_status_label(checked):
            if checked:
                self.lbl_proxy_status.setText("代理状态: 未测试")
                self.lbl_proxy_status.setStyleSheet("color: #748297;")
            else:
                self.lbl_proxy_status.setText("代理状态: 系统代理模式")
                self.lbl_proxy_status.setStyleSheet("color: #FF5924;")
        self.chk_custom_proxy.toggled.connect(update_proxy_status_label)

        # Cookie 导入
        left_layout.addWidget(QLabel("JAVDB Cookie (可选):"))
        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText("在此粘贴 JAVDB 网页登录后的 Cookie 字符串...")
        self.cookie_input.setFixedHeight(120)
        left_layout.addWidget(self.cookie_input)
        self.btn_save_cookie = QPushButton("保存 Cookie")
        left_layout.addWidget(self.btn_save_cookie)

        # 保存路径
        left_layout.addWidget(QLabel("保存目标路径:"))
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        left_layout.addWidget(self.path_input)
        self.btn_browse = QPushButton("浏览并选择路径...")
        left_layout.addWidget(self.btn_browse)

        # 所有权展示与免责声明
        self.lbl_copyright = QLabel(
            "<div style='text-align: center; margin-top: 15px; border-top: 1px solid #E5EAF2; padding-top: 12px;'>"
            "  <div style='color: #748297; font-size: 11px; margin-bottom: 4px;'><b>所有权归属</b></div>"
            "  <div style='color: #FF5924; font-size: 11px; font-weight: bold; margin-bottom: 6px;'>"
            "    <a href='https://github.com/sangokvip/JAV-Scraper' style='color: #FF5924; text-decoration: none;'>GitHub: JAV-Scraper</a>"
            "  </div>"
            "  <div style='color: #748297; font-size: 10px; line-height: 1.4;'>"
            "    仅供学习交流使用<br><b>严禁用于任何商业用途</b>"
            "  </div>"
            "</div>"
        )
        self.lbl_copyright.setObjectName("CopyrightLabel")
        self.lbl_copyright.setOpenExternalLinks(True)
        left_layout.addWidget(self.lbl_copyright)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # ================== 中间：任务区 ==================
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)

        # 拖拽占位盘 / 提示
        self.drop_label = ClickableDropLabel("拖入视频文件或整个文件夹至此，或点击此处选择视频\n(支持批量自动识别番号并校对)")
        self.drop_label.setObjectName("DropZone")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setFixedHeight(100)
        self.drop_label.setCursor(Qt.CursorShape.PointingHandCursor)
        center_layout.addWidget(self.drop_label)

        # 任务表格
        self.table = TaskTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "原文件名", "识别番号 (可双击编辑)", "当前状态"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 150)
        self.table.verticalHeader().setVisible(False)
        center_layout.addWidget(self.table)

        # 无任务占位提示区
        self.empty_placeholder = QWidget()
        self.empty_placeholder.setObjectName("EmptyPlaceholder")
        ep_layout = QVBoxLayout(self.empty_placeholder)
        ep_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_icon = QLabel("🎬")
        lbl_icon.setStyleSheet("font-size: 42px; margin-bottom: 8px; background-color: transparent;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_title = QLabel("开启您的影片极速整理之旅")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FF5924; margin-bottom: 5px; background-color: transparent;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_desc = QLabel("将视频文件或文件夹拖拽至上方虚线盘，或者直接双击表格行编辑番号即可开始。")
        lbl_desc.setStyleSheet("font-size: 12px; color: #748297; line-height: 1.4; background-color: transparent;")
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setFixedWidth(400)
        
        ep_layout.addWidget(lbl_icon)
        ep_layout.addWidget(lbl_title)
        ep_layout.addWidget(lbl_desc)
        center_layout.addWidget(self.empty_placeholder)

        # 操作按钮控制栏
        btn_control_layout = QVBoxLayout()
        btn_control_layout.setSpacing(6)

        # 按钮行 1：导入与清空
        btn_row1_layout = QHBoxLayout()
        self.btn_clear = QPushButton("一键清空")
        self.btn_clear.setObjectName("ClearBtn")
        self.btn_remove_selected = QPushButton("移除所选")
        self.btn_remove_selected.setObjectName("RemoveSelectedBtn")
        self.btn_retry_failed = QPushButton("重试失败")
        self.btn_retry_failed.setObjectName("RetryFailedBtn")
        self.btn_import_dir = QPushButton("导入文件夹...")
        self.btn_import_dir.setObjectName("ImportDirBtn")
        self.btn_add_code = QPushButton("手动输入番号...")
        self.btn_add_code.setObjectName("AddCodeBtn")
        btn_row1_layout.addWidget(self.btn_clear)
        btn_row1_layout.addWidget(self.btn_remove_selected)
        btn_row1_layout.addWidget(self.btn_retry_failed)
        btn_row1_layout.addWidget(self.btn_import_dir)
        btn_row1_layout.addWidget(self.btn_add_code)
        btn_control_layout.addLayout(btn_row1_layout)

        # 按钮行 2：仅刮削与整理动作
        btn_row2_layout = QHBoxLayout()
        self.btn_start = QPushButton("仅执行刮削预览")
        self.btn_start.setObjectName("StartBtn")
        self.btn_organize = QPushButton("执行整理落盘")
        self.btn_organize.setObjectName("OrganizeBtn")
        btn_row2_layout.addWidget(self.btn_start)
        btn_row2_layout.addWidget(self.btn_organize)
        btn_control_layout.addLayout(btn_row2_layout)

        center_layout.addLayout(btn_control_layout)

        main_layout.addWidget(center_panel, stretch=1)

        # ================== 右侧：预览卡片 ==================
        right_panel = QWidget()
        right_panel.setObjectName("RightPanel")
        right_panel.setFixedWidth(320)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        self.lbl_cover = QLabel("选择影片以预览海报")
        self.lbl_cover.setObjectName("CoverPreview")
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setFixedHeight(340)
        right_layout.addWidget(self.lbl_cover)

        # 引入只读垂直详情滚动区，包裹所有文字、剧照与磁力链接，彻底从物理层解耦空间争抢
        from PySide6.QtWidgets import QScrollArea
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setObjectName("DetailScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.detail_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.detail_scroll.setStyleSheet("background-color: transparent; border: none;")

        detail_container = QWidget()
        detail_container.setObjectName("DetailContainer")
        detail_container.setStyleSheet("background-color: transparent;")
        detail_container_layout = QVBoxLayout(detail_container)
        detail_container_layout.setContentsMargins(0, 12, 0, 0)
        detail_container_layout.setSpacing(10)

        self.lbl_info_title = QLabel("影片番号与标题")
        self.lbl_info_title.setObjectName("InfoTitle")
        self.lbl_info_title.setWordWrap(True)
        detail_container_layout.addWidget(self.lbl_info_title)

        self.lbl_info_details = QLabel("制片商: -\n发行日期: -\n演员: -")
        self.lbl_info_details.setObjectName("InfoDetails")
        self.lbl_info_details.setWordWrap(True)
        detail_container_layout.addWidget(self.lbl_info_details)

        # 剧照横向滚动区域
        self.lbl_samples_title = QLabel("影片预览剧照 (点击放大):")
        self.lbl_samples_title.setObjectName("SamplesTitle")
        detail_container_layout.addWidget(self.lbl_samples_title)

        self.samples_scroll = QScrollArea()
        self.samples_scroll.setObjectName("SamplesScroll")
        self.samples_scroll.setWidgetResizable(True)
        self.samples_scroll.setFixedHeight(110)
        self.samples_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.samples_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.samples_widget = QWidget()
        self.samples_layout = QHBoxLayout(self.samples_widget)
        self.samples_layout.setContentsMargins(5, 2, 5, 2)
        self.samples_layout.setSpacing(8)
        self.samples_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.samples_scroll.setWidget(self.samples_widget)
        detail_container_layout.addWidget(self.samples_scroll)

        # 磁力链接展示区域
        self.lbl_magnet_title = QLabel("磁力链接 (点击复制):")
        self.lbl_magnet_title.setObjectName("MagnetTitle")
        detail_container_layout.addWidget(self.lbl_magnet_title)

        self.table_magnet = QTableWidget(0, 3)
        self.table_magnet.setHorizontalHeaderLabels(["大小", "日期", "操作"])
        self.table_magnet.setObjectName("MagnetTable")
        self.table_magnet.setFixedHeight(120)
        self.table_magnet.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_magnet.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_magnet.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table_magnet.setColumnWidth(1, 95)
        self.table_magnet.setColumnWidth(2, 60)
        self.table_magnet.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_magnet.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_magnet.verticalHeader().setVisible(False)
        self.table_magnet.horizontalHeader().setSectionsClickable(True)
        detail_container_layout.addWidget(self.table_magnet)

        detail_container_layout.addStretch()
        self.detail_scroll.setWidget(detail_container)
        
        right_layout.addWidget(self.detail_scroll)
        main_layout.addWidget(right_panel)

        # 启用窗口拖入
        self.setAcceptDrops(True)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QWidget {
                color: #1A1C2E;
                font-family: "Inter", "SF Pro Display", "PingFang SC", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            #LeftPanel, #RightPanel {
                background-color: #F5F7F9;
                border-radius: 16px;
                border: 1px solid #E5EAF2;
            }
            QLabel {
                font-weight: bold;
                color: #1A1C2E;
            }
            QLineEdit, QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 8px;
                padding: 6px 10px;
                color: #1A1C2E;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1.5px solid #FF5924;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1.5px solid #E5EAF2;
                border-radius: 20px;
                padding: 8px 16px;
                font-weight: 600;
                color: #4A5465;
            }
            QPushButton:hover {
                background-color: #F5F7F9;
                border-color: #FF5924;
                color: #1A1C2E;
            }
            QPushButton:pressed {
                background-color: #E5EAF2;
                padding-top: 9px;
                padding-bottom: 7px;
            }
            #StartBtn {
                background-color: transparent;
                border: 1.5px solid #FF5924;
                color: #FF5924;
            }
            #StartBtn:hover {
                background-color: rgba(255, 89, 36, 0.08);
                color: #FF8550;
                border-color: #FF8550;
            }
            #StartBtn:pressed {
                background-color: rgba(255, 89, 36, 0.15);
                padding-top: 9px;
                padding-bottom: 7px;
            }
            #AddCodeBtn {
                background-color: transparent;
                border: 1.5px solid #E5EAF2;
                color: #4A5465;
            }
            #AddCodeBtn:hover {
                background-color: #F5F7F9;
                border-color: #FF5924;
                color: #1A1C2E;
            }
            #OrganizeBtn {
                background-color: #FF5924;
                color: #FFFFFF;
                border: 1px solid #FF5924;
                border-radius: 20px;
            }
            #OrganizeBtn:hover {
                background-color: #FF8550;
                border-color: #FF8550;
            }
            #OrganizeBtn:pressed {
                background-color: #E04414;
                border-color: #E04414;
                padding-top: 9px;
                padding-bottom: 7px;
            }
            #SamplesScroll {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 12px;
            }
            #SamplesTitle {
                color: #FF5924;
                font-size: 12px;
                margin-top: 5px;
            }
            #CustomProxyCheck {
                color: #1A1C2E;
                font-weight: bold;
            }
            #MagnetTitle {
                color: #FF5924;
                font-size: 12px;
                margin-top: 5px;
            }
            #MagnetTable {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 12px;
                gridline-color: #E5EAF2;
            }
            #MagnetTable::item {
                color: #1A1C2E;
                padding: 4px;
            }
            #CopyMagnetBtn {
                background-color: #FF5924;
                color: #FFFFFF;
                border: 1px solid #FF5924;
                border-radius: 12px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            #CopyMagnetBtn:hover {
                background-color: #FF8550;
                border-color: #FF8550;
            }
            #CopyMagnetBtn:pressed {
                background-color: #E04414;
                border-color: #E04414;
            }
            #RemoveSelectedBtn {
                background-color: transparent;
                border: 1.5px solid #E5EAF2;
                color: #FF453A;
            }
            #RemoveSelectedBtn:hover {
                background-color: rgba(255, 69, 58, 0.08);
                border-color: #FF453A;
            }
            #RemoveSelectedBtn:pressed {
                background-color: rgba(255, 69, 58, 0.15);
                padding-top: 9px;
                padding-bottom: 7px;
            }
            #RetryFailedBtn {
                background-color: transparent;
                border: 1.5px solid #E5A73B;
                color: #E5A73B;
            }
            #RetryFailedBtn:hover {
                background-color: rgba(229, 167, 59, 0.08);
                color: #F0B849;
                border-color: #F0B849;
            }
            #RetryFailedBtn:pressed {
                background-color: rgba(229, 167, 59, 0.15);
                padding-top: 9px;
                padding-bottom: 7px;
            }
            #DropZone {
                border: 2px dashed #D4DCE5;
                border-radius: 12px;
                background-color: #F5F7F9;
                color: #748297;
                font-size: 14px;
            }
            #DropZone:hover {
                border-color: #FF5924;
                background-color: #FFF1F1;
            }
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #F5F7F9;
                gridline-color: #E5EAF2;
                border: 1px solid #E5EAF2;
                border-radius: 12px;
            }
            QTableWidget::item {
                color: #1A1C2E;
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #F0F2F5;
                color: #4A5465;
                padding: 6px;
                border: 1px solid #E5EAF2;
                font-weight: bold;
            }
            #CoverPreview {
                background-color: #F5F7F9;
                border: 1px solid #E5EAF2;
                border-radius: 16px;
                color: #748297;
            }
            #InfoTitle {
                font-family: "Lora", "Georgia", "Times New Roman", serif;
                font-size: 13px;
                color: #FF5924;
                font-weight: bold;
            }
            #InfoDetails {
                color: #4A5465;
                line-height: 1.5;
            }
            QMessageBox, QDialog, QInputDialog {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 16px;
            }
            QMessageBox QLabel, QInputDialog QLabel {
                color: #1A1C2E;
                font-size: 13px;
            }
            QMessageBox QPushButton, QInputDialog QPushButton {
                background-color: #FFFFFF;
                border: 1.5px solid #E5EAF2;
                color: #4A5465;
                padding: 6px 14px;
                font-weight: bold;
                border-radius: 15px;
                min-width: 75px;
            }
            QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
                background-color: #F5F7F9;
                border-color: #FF5924;
                color: #1A1C2E;
            }
            QTableWidget QLineEdit {
                padding: 0px;
                border: 1px solid #FF5924;
                border-radius: 0px;
                background-color: #FFFFFF;
                color: #1A1C2E;
            }
            #EmptyPlaceholder {
                border: 2px dashed #D4DCE5;
                border-radius: 12px;
                background-color: #F5F7F9;
            }
            #CopyrightLabel {
                background-color: transparent;
            }
            #CopyrightLabel a {
                color: #FF5924;
                font-weight: bold;
                text-decoration: none;
            }
            #CopyrightLabel a:hover {
                color: #FF8550;
                text-decoration: underline;
            }
        """)

    def update_empty_placeholder_visibility(self, is_empty: bool):
        if is_empty:
            self.table.hide()
            self.empty_placeholder.show()
        else:
            self.table.show()
            self.empty_placeholder.hide()

    # 拖拽事件捕获
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_label.setStyleSheet("border-color: #FF5924; background-color: rgba(255, 89, 36, 0.08);")

    def dragLeaveEvent(self, event):
        self.drop_label.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.exists(local_path):
                paths.append(local_path)
        if paths:
            self.files_dropped.emit(paths)
        self.drop_label.setStyleSheet("")
