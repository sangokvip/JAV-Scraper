import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit, QTextEdit,
    QFileDialog, QAbstractItemView, QHeaderView, QRadioButton, QButtonGroup,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap

class MainWindow(QMainWindow):
    files_dropped = Signal(list)  # 拖入的文件路径列表

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JAVDB API Scraper GUI")
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

        # 联动更新提示状态和颜色
        def update_proxy_status_label(checked):
            if checked:
                self.lbl_proxy_status.setText("代理状态: 未测试")
                self.lbl_proxy_status.setStyleSheet("color: #8E8E93;")
            else:
                self.lbl_proxy_status.setText("代理状态: 系统代理模式")
                self.lbl_proxy_status.setStyleSheet("color: #D4AF37;")
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

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # ================== 中间：任务区 ==================
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)

        # 拖拽占位盘 / 提示
        self.drop_label = QLabel("拖入视频文件或整个文件夹至此\n(支持批量自动识别番号并校对)")
        self.drop_label.setObjectName("DropZone")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setFixedHeight(100)
        center_layout.addWidget(self.drop_label)

        # 任务表格
        self.table = QTableWidget(0, 4)
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

        # 操作按钮控制栏
        btn_control_layout = QVBoxLayout()
        btn_control_layout.setSpacing(6)

        # 按钮行 1：导入与清空
        btn_row1_layout = QHBoxLayout()
        self.btn_clear = QPushButton("一键清空")
        self.btn_clear.setObjectName("ClearBtn")
        self.btn_import_files = QPushButton("导入视频文件...")
        self.btn_import_files.setObjectName("ImportFilesBtn")
        self.btn_import_dir = QPushButton("导入文件夹...")
        self.btn_import_dir.setObjectName("ImportDirBtn")
        self.btn_add_code = QPushButton("手动输入番号...")
        self.btn_add_code.setObjectName("AddCodeBtn")
        btn_row1_layout.addWidget(self.btn_clear)
        btn_row1_layout.addWidget(self.btn_import_files)
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
        right_layout.setSpacing(10)

        self.lbl_cover = QLabel("选择影片以预览海报")
        self.lbl_cover.setObjectName("CoverPreview")
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setFixedHeight(380)
        right_layout.addWidget(self.lbl_cover)

        self.lbl_info_title = QLabel("影片番号与标题")
        self.lbl_info_title.setObjectName("InfoTitle")
        self.lbl_info_title.setWordWrap(True)
        right_layout.addWidget(self.lbl_info_title)

        self.lbl_info_details = QLabel("制片商: -\n发行日期: -\n演员: -")
        self.lbl_info_details.setObjectName("InfoDetails")
        self.lbl_info_details.setWordWrap(True)
        right_layout.addWidget(self.lbl_info_details)

        # 剧照横向滚动区域
        self.lbl_samples_title = QLabel("影片预览剧照 (点击放大):")
        self.lbl_samples_title.setObjectName("SamplesTitle")
        right_layout.addWidget(self.lbl_samples_title)

        from PySide6.QtWidgets import QScrollArea
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
        right_layout.addWidget(self.samples_scroll)

        # 磁力链接展示区域
        self.lbl_magnet_title = QLabel("磁力链接 (点击复制):")
        self.lbl_magnet_title.setObjectName("MagnetTitle")
        right_layout.addWidget(self.lbl_magnet_title)

        self.table_magnet = QTableWidget(0, 2)
        self.table_magnet.setHorizontalHeaderLabels(["大小", "操作"])
        self.table_magnet.setObjectName("MagnetTable")
        self.table_magnet.setFixedHeight(120)
        self.table_magnet.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_magnet.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_magnet.setColumnWidth(1, 70)
        self.table_magnet.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_magnet.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_magnet.verticalHeader().setVisible(False)
        right_layout.addWidget(self.table_magnet)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        # 启用窗口拖入
        self.setAcceptDrops(True)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
            }
            QWidget {
                color: #F5F5F7;
                font-family: "SF Pro Display", "PingFang SC", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            #LeftPanel, #RightPanel {
                background-color: #1E1E1E;
                border-radius: 8px;
                border: 1px solid #2C2C2C;
            }
            QLabel {
                font-weight: bold;
            }
            QLineEdit, QTextEdit {
                background-color: #2A2A2A;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 6px;
                color: #F5F5F7;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #D4AF37;
            }
            QPushButton {
                background-color: #2E2E2E;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: bold;
                color: #F5F5F7;
            }
            QPushButton:hover {
                background-color: #3E3E3E;
                border-color: #D4AF37;
            }
            #StartBtn {
                background-color: #2E2E2E;
                border: 1px solid #D4AF37;
                color: #D4AF37;
            }
            #StartBtn:hover {
                background-color: #3E3E3E;
                color: #E5C158;
            }
            #AddCodeBtn {
                background-color: #2E2E2E;
                border: 1px solid #444444;
                color: #F5F5F7;
            }
            #AddCodeBtn:hover {
                background-color: #3E3E3E;
                border-color: #D4AF37;
            }
            #OrganizeBtn {
                background-color: #D4AF37;
                color: #121212;
                border: none;
            }
            #OrganizeBtn:hover {
                background-color: #E5C158;
            }
            #SamplesScroll {
                background-color: #2A2A2A;
                border: 1px solid #3A3A3A;
                border-radius: 6px;
            }
            #SamplesTitle {
                color: #D4AF37;
                font-size: 12px;
                margin-top: 5px;
            }
            #CustomProxyCheck {
                color: #F5F5F7;
                font-weight: bold;
            }
            #MagnetTitle {
                color: #D4AF37;
                font-size: 12px;
                margin-top: 5px;
            }
            #MagnetTable {
                background-color: #2A2A2A;
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                gridline-color: #3A3A3A;
            }
            #MagnetTable::item {
                color: #F5F5F7;
                padding: 4px;
            }
            #CopyMagnetBtn {
                background-color: #D4AF37;
                color: #121212;
                border: none;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: bold;
            }
            #CopyMagnetBtn:hover {
                background-color: #E5C158;
            }
            #DropZone {
                border: 2px dashed #444444;
                border-radius: 8px;
                background-color: #1E1E1E;
                color: #8E8E93;
                font-size: 14px;
            }
            #DropZone:hover {
                border-color: #D4AF37;
                background-color: #252525;
            }
            QTableWidget {
                background-color: #1E1E1E;
                alternate-background-color: #252525;
                gridline-color: #2C2C2C;
                border: 1px solid #2C2C2C;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #2E2E2E;
                color: #F5F5F7;
                padding: 5px;
                border: 1px solid #2C2C2C;
                font-weight: bold;
            }
            #CoverPreview {
                background-color: #2A2A2A;
                border: 1px solid #3A3A3A;
                border-radius: 6px;
                color: #8E8E93;
            }
            #InfoTitle {
                font-size: 16px;
                color: #D4AF37;
                font-weight: bold;
            }
            #InfoDetails {
                color: #8E8E93;
                line-height: 1.5;
            }
            QMessageBox, QDialog, QInputDialog {
                background-color: #1E1E1E;
            }
            QMessageBox QLabel, QInputDialog QLabel {
                color: #F5F5F7;
                font-size: 13px;
            }
            QMessageBox QPushButton, QInputDialog QPushButton {
                background-color: #2E2E2E;
                border: 1px solid #444444;
                color: #F5F5F7;
                padding: 6px 12px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 65px;
            }
            QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
                background-color: #3E3E3E;
                border-color: #D4AF37;
            }
        """)

    # 拖拽事件捕获
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_label.setStyleSheet("border-color: #D4AF37; background-color: #252525;")

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
