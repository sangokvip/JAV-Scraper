import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QFileDialog, QAbstractItemView, QHeaderView, QRadioButton, QButtonGroup,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QIcon
from gui.widgets import TaskTableWidget, ClickableDropLabel
from gui.styles import STYLE_SHEET

class MainWindow(QMainWindow):
    files_dropped = Signal(list)  # 拖入的文件路径列表

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JAV SCRAPER")
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.resize(1180, 750)
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
        left_panel.setFixedWidth(270)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 8, 12, 8)
        left_layout.setSpacing(7)


        # ⚠️ VPN 必要性提示
        vpn_notice = QLabel("⚠️  刮削需要 VPN 代理\n请确保已开启 VPN，否则无法连接至 JAVDB。")
        vpn_notice.setObjectName("VpnNoticeLabel")
        vpn_notice.setWordWrap(True)
        vpn_notice.setStyleSheet(
            "background-color: rgba(255, 89, 36, 0.12);"
            "color: #FF5924;"
            "border: 1px solid rgba(255, 89, 36, 0.4);"
            "border-radius: 6px;"
            "padding: 8px 10px;"
            "font-size: 11px;"
            "font-weight: 500;"
            "line-height: 1.5;"
        )
        left_layout.addWidget(vpn_notice)

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

        # Cookie 导入 — 单行输入 + 行内保存按钮
        cookie_row_layout = QHBoxLayout()
        cookie_row_layout.setSpacing(6)
        cookie_label = QLabel("JAVDB Cookie (可选):")
        cookie_row_layout.addWidget(cookie_label)
        cookie_row_layout.addStretch()
        self.btn_save_cookie = QPushButton("保存")
        self.btn_save_cookie.setObjectName("SaveCookieInlineBtn")
        self.btn_save_cookie.setFixedHeight(22)
        self.btn_save_cookie.setStyleSheet(
            "QPushButton#SaveCookieInlineBtn {"
            "  background-color: transparent;"
            "  border: 1px solid #E5EAF2;"
            "  border-radius: 10px;"
            "  padding: 2px 10px;"
            "  font-size: 11px;"
            "  color: #4A5465;"
            "  font-weight: 600;"
            "}"
            "QPushButton#SaveCookieInlineBtn:hover {"
            "  border-color: #FF5924;"
            "  color: #FF5924;"
            "}"
        )
        cookie_row_layout.addWidget(self.btn_save_cookie)
        left_layout.addLayout(cookie_row_layout)
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("粘贴 JAVDB Cookie...")
        self.cookie_input.setEchoMode(QLineEdit.EchoMode.Password)
        left_layout.addWidget(self.cookie_input)

        # 保存路径
        left_layout.addWidget(QLabel("保存目标路径:"))
        self.path_input = QLineEdit()
        left_layout.addWidget(self.path_input)
        self.btn_browse = QPushButton("浏览并选择路径...")
        left_layout.addWidget(self.btn_browse)

        # 高级命名模板
        left_layout.addWidget(QLabel("归档命名模板:"))
        self.tmpl_input = QLineEdit("{actor}/{[code]} {title}")
        self.tmpl_input.setObjectName("TemplateInput")
        left_layout.addWidget(self.tmpl_input)

        # 动态效果预览标签
        self.lbl_tmpl_example = QLabel()
        self.lbl_tmpl_example.setObjectName("TemplateExampleLabel")
        self.lbl_tmpl_example.setWordWrap(True)
        left_layout.addWidget(self.lbl_tmpl_example)

        # 变量芯片（点击自动插入光标处）
        chip_vars = [
            ("{actor}", "主演"),
            ("{studio}", "片商"),
            ("{code}", "番号"),
            ("{title}", "标题"),
            ("{year}", "年份"),
            ("{date}", "日期"),
        ]
        chip_row = QHBoxLayout()
        chip_row.setSpacing(3)
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_style = (
            "QPushButton {"
            "  background-color: rgba(255,89,36,0.08);"
            "  border: 1px solid rgba(255,89,36,0.35);"
            "  border-radius: 10px;"
            "  padding: 2px 5px;"
            "  font-size: 11px;"
            "  color: #FF5924;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background-color: rgba(255,89,36,0.18);"
            "  border-color: #FF5924;"
            "}"
        )
        for var, label in chip_vars:
            chip_btn = QPushButton(f"{label}")
            chip_btn.setToolTip(f"点击插入 {var}")
            chip_btn.setStyleSheet(chip_style)
            chip_btn.setFixedHeight(22)
            chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            chip_btn.clicked.connect(lambda _, v=var: self._insert_template_var(v))
            chip_row.addWidget(chip_btn)
        chip_row.addStretch()
        left_layout.addLayout(chip_row)

        # 整理首选项
        left_layout.addWidget(QLabel("整理首选项:"))
        self.chk_download_samples = QCheckBox("下载影片剧照 (Sample Photos)")
        self.chk_download_samples.setChecked(True)
        left_layout.addWidget(self.chk_download_samples)
        
        self.chk_subtitle_tag = QCheckBox("在 NFO 中写入中文字幕标签")
        self.chk_subtitle_tag.setChecked(True)
        left_layout.addWidget(self.chk_subtitle_tag)

        # 所有权展示与免责声明
        self.lbl_copyright = QLabel(
            "<div style='text-align: center; margin-top: 4px; border-top: 1px solid #E5EAF2; padding-top: 4px;'>"
            "  <div style='color: #748297; font-size: 11px; margin-bottom: 2px;'><b>所有权归属</b></div>"
            "  <div style='color: #FF5924; font-size: 11px; font-weight: bold; margin-bottom: 2px;'>"
            "    <a href='https://github.com/sangokvip/JAV-Scraper' style='color: #FF5924; text-decoration: none;'>GitHub: JAV-Scraper</a>"
            "  </div>"
            "  <div style='color: #748297; font-size: 10px; line-height: 1.3;'>"
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

        # === 搜索过滤栏 ===
        self.filter_widget = QWidget()
        self.filter_widget.setObjectName("FilterWidget")
        filter_layout = QHBoxLayout(self.filter_widget)
        filter_layout.setContentsMargins(0, 5, 0, 5)
        filter_layout.setSpacing(8)
        
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("🔍 输入文件名或番号进行过滤...")
        filter_layout.addWidget(self.search_input, stretch=1)
        
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.btn_filter_all = QPushButton("全部")
        self.btn_filter_all.setCheckable(True)
        self.btn_filter_all.setProperty("class", "PillFilter")
        self.btn_filter_all.setChecked(True)
        
        self.btn_filter_pending = QPushButton("待整理")
        self.btn_filter_pending.setCheckable(True)
        self.btn_filter_pending.setProperty("class", "PillFilter")
        
        self.btn_filter_running = QPushButton("进行中")
        self.btn_filter_running.setCheckable(True)
        self.btn_filter_running.setProperty("class", "PillFilter")
        
        self.btn_filter_success = QPushButton("已成功")
        self.btn_filter_success.setCheckable(True)
        self.btn_filter_success.setProperty("class", "PillFilter")
        
        self.btn_filter_failed = QPushButton("失败项")
        self.btn_filter_failed.setCheckable(True)
        self.btn_filter_failed.setProperty("class", "PillFilter")
        
        self.filter_group.addButton(self.btn_filter_all, 0)
        self.filter_group.addButton(self.btn_filter_pending, 1)
        self.filter_group.addButton(self.btn_filter_running, 2)
        self.filter_group.addButton(self.btn_filter_success, 3)
        self.filter_group.addButton(self.btn_filter_failed, 4)
        
        filter_layout.addWidget(self.btn_filter_all)
        filter_layout.addWidget(self.btn_filter_pending)
        filter_layout.addWidget(self.btn_filter_running)
        filter_layout.addWidget(self.btn_filter_success)
        filter_layout.addWidget(self.btn_filter_failed)
        
        center_layout.addWidget(self.filter_widget)

        # 任务表格
        self.table = TaskTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "原文件名", "识别番号 (可双击编辑)", "当前状态"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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

        # 详情滚动区
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

        self.setAcceptDrops(True)
        
        # 绑定模板实时中文效果预览
        self.tmpl_input.textChanged.connect(self.update_template_preview)
        self.update_template_preview()

    def apply_stylesheet(self):
        self.setStyleSheet(STYLE_SHEET)

    def update_empty_placeholder_visibility(self, is_empty: bool):
        if is_empty:
            self.table.hide()
            self.filter_widget.hide()
            self.empty_placeholder.show()
        else:
            self.table.show()
            self.filter_widget.show()
            self.empty_placeholder.hide()

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

    def _insert_template_var(self, var: str):
        """将变量芯片插入模板输入框的当前光标位置"""
        cur_text = self.tmpl_input.text()
        pos = self.tmpl_input.cursorPosition()
        new_text = cur_text[:pos] + var + cur_text[pos:]
        self.tmpl_input.setText(new_text)
        self.tmpl_input.setCursorPosition(pos + len(var))
        self.tmpl_input.setFocus()

    def update_template_preview(self):
        """更新并渲染命名模板的中文示例效果"""
        tmpl = self.tmpl_input.text()
        sample_data = {
            "actor": "三上悠亚",
            "studio": "S1",
            "code": "SSNI-001",
            "title": "经典作品",
            "year": "2023",
            "date": "2023-01-01"
        }
        preview = tmpl
        for k, v in sample_data.items():
            preview = preview.replace(f"{{{k}}}", v)
        self.lbl_tmpl_example.setText(f"预览: {preview}")
