import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QRadioButton, QButtonGroup, QListWidget, QWidget,
    QTabWidget, QSpinBox, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon

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

class ClickableLabel(QLabel):
    clicked = Signal(QLabel)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap_data = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.pixmap_data:
                self.clicked.emit(self)

class PhotoDialog(QDialog):
    def __init__(self, pixmaps, current_index, parent=None):
        super().__init__(parent)
        self.pixmaps = pixmaps
        self.current_index = current_index
        self.setWindowTitle("剧照放大预览")
        self.setFixedSize(920, 650)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        middle_layout = QHBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(15)
        
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setObjectName("PrevPhotoBtn")
        self.btn_prev.clicked.connect(self.show_prev)
        
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setFixedSize(800, 560)
        
        self.btn_next = QPushButton("▶")
        self.btn_next.setObjectName("NextPhotoBtn")
        self.btn_next.clicked.connect(self.show_next)
        
        middle_layout.addWidget(self.btn_prev)
        middle_layout.addWidget(self.lbl_image)
        middle_layout.addWidget(self.btn_next)
        main_layout.addLayout(middle_layout)
        
        self.lbl_info = QLabel()
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setStyleSheet("color: #FF5924; font-weight: bold; font-size: 12px; margin-top: 2px;")
        main_layout.addWidget(self.lbl_info)
        
        self.update_view()
        
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
        scaled = pixmap.scaled(800, 560, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_image.setPixmap(scaled)
        
        self.lbl_info.setText(f"剧照预览：{self.current_index + 1} / {len(self.pixmaps)}")
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
        if event.key() == Qt.Key.Key_Left:
            self.show_prev()
        elif event.key() == Qt.Key.Key_Right:
            self.show_next()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self.lbl_image.geometry().contains(pos):
                self.accept()

class ConflictResolutionDialog(QDialog):
    """
    当扫描到存在命名/番号目录重名冲突时弹出，让用户决定处理冲突的默认行为。
    """
    def __init__(self, conflicting_items: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("归档目录冲突预检")
        self.setFixedSize(520, 360)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        # 头部提示
        title_lbl = QLabel("⚠️ 发现重名冲突影片")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FF5924;")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("下列番号在目标保存目录下已存在归档文件夹，请选择处理行为：")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #4A5465; font-size: 12px;")
        layout.addWidget(desc_lbl)
        
        # 冲突列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #F5F7F9;
                border: 1px solid #E5EAF2;
                border-radius: 8px;
                padding: 5px;
                color: #1A1C2E;
                font-size: 11px;
            }
        """)
        for _, code, target in conflicting_items:
            self.list_widget.addItem(f"番号 [{code}] ➜ 归档于: {os.path.basename(target)}")
        layout.addWidget(self.list_widget)
        
        # 冲突行为选择
        choices_widget = QWidget()
        choices_layout = QVBoxLayout(choices_widget)
        choices_layout.setContentsMargins(0, 5, 0, 5)
        choices_layout.setSpacing(8)
        
        self.bg = QButtonGroup(self)
        
        self.r_overwrite = QRadioButton("覆盖原有视频文件")
        self.r_keep_both = QRadioButton("保留两者 (新移动视频追加『_副本』后缀)")
        self.r_only_meta = QRadioButton("仅更新元数据与剧照 (不移动新视频文件)")
        self.r_skip = QRadioButton("跳过这些冲突影片的整理")
        
        # 默认选中“保留两者”或者“仅更新元数据”
        self.r_keep_both.setChecked(True)
        
        self.bg.addButton(self.r_overwrite, 0)
        self.bg.addButton(self.r_keep_both, 1)
        self.bg.addButton(self.r_only_meta, 2)
        self.bg.addButton(self.r_skip, 3)
        
        choices_layout.addWidget(self.r_keep_both)
        choices_layout.addWidget(self.r_only_meta)
        choices_layout.addWidget(self.r_overwrite)
        choices_layout.addWidget(self.r_skip)
        layout.addWidget(choices_widget)
        
        # 底部确定取消按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_ok = QPushButton("确认整理")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #FF5924;
                color: white;
                border: 1px solid #FF5924;
                border-radius: 16px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF8550;
                border-color: #FF8550;
            }
        """)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def selected_resolution(self) -> str:
        idx = self.bg.checkedId()
        if idx == 0:
            return "overwrite"
        elif idx == 1:
            return "keep_both"
        elif idx == 2:
            return "only_meta"
        else:
            return "skip"

class MultiCodeInputDialog(QDialog):
    """
    手动批量导入番号对话框。
    - Tab 1：直接粘贴/输入多行或以各类空格逗号分隔的番号列表。
    - Tab 2：输入关键字搜索平台，抓取返回的番号导入。
    """
    search_requested = Signal(str, int)  # keyword, page

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("手动批量添加番号")
        self.setFixedSize(520, 440)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # 创建 Tab Widget
        self.tabs = QTabWidget()
        
        # Tab 1: 直接贴入
        self.tab_paste = QWidget()
        paste_layout = QVBoxLayout(self.tab_paste)
        paste_layout.setContentsMargins(10, 10, 10, 10)
        paste_layout.setSpacing(8)
        
        lbl_paste = QLabel("在下方输入或粘贴番号 (支持空格、逗号、分号或换行分隔多个番号)：")
        lbl_paste.setWordWrap(True)
        lbl_paste.setStyleSheet("color: #4A5465; font-size: 11px; font-weight: normal; background-color: transparent;")
        
        self.txt_codes = QTextEdit()
        self.txt_codes.setPlaceholderText("例如:\nIPX-123, IPX-124\nIPX-125 VDD-126")
        
        paste_layout.addWidget(lbl_paste)
        paste_layout.addWidget(self.txt_codes)
        self.tabs.addTab(self.tab_paste, "📂 直接贴入番号")
        
        # Tab 2: 平台系列搜索
        self.tab_search = QWidget()
        search_layout = QVBoxLayout(self.tab_search)
        search_layout.setContentsMargins(10, 10, 10, 10)
        search_layout.setSpacing(12)
        
        lbl_search = QLabel("输入关键字（如系列或番号前缀），搜索平台上的番号并批量导入：")
        lbl_search.setWordWrap(True)
        lbl_search.setStyleSheet("color: #4A5465; font-size: 11px; font-weight: normal; background-color: transparent;")
        
        search_input_layout = QHBoxLayout()
        search_input_layout.setSpacing(8)
        
        self.txt_keyword = QLineEdit()
        self.txt_keyword.setPlaceholderText("输入关键字，例如 VDD, IPX, SSIS...")
        
        self.spin_page = QSpinBox()
        self.spin_page.setRange(1, 10)
        self.spin_page.setValue(1)
        self.spin_page.setSuffix(" 页")
        
        self.btn_search = QPushButton("搜索番号")
        self.btn_search.setObjectName("SearchCodesBtn")
        self.btn_search.setStyleSheet("""
            QPushButton#SearchCodesBtn {
                background-color: #FF5924;
                color: white;
                border: 1px solid #FF5924;
                border-radius: 15px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton#SearchCodesBtn:hover {
                background-color: #FF8550;
                border-color: #FF8550;
            }
        """)
        self.btn_search.clicked.connect(self.on_search_clicked)
        
        search_input_layout.addWidget(self.txt_keyword, stretch=1)
        search_input_layout.addWidget(self.spin_page)
        search_input_layout.addWidget(self.btn_search)
        
        self.lbl_search_status = QLabel("")
        self.lbl_search_status.setWordWrap(True)
        self.lbl_search_status.setStyleSheet("color: #FF5924; font-size: 11px; font-weight: bold; background-color: transparent;")
        
        search_layout.addWidget(lbl_search)
        search_layout.addLayout(search_input_layout)
        search_layout.addWidget(self.lbl_search_status)
        search_layout.addStretch()
        
        self.tabs.addTab(self.tab_search, "🔍 平台系列搜索")
        
        layout.addWidget(self.tabs)
        
        # 底部确定取消按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_ok = QPushButton("确认导入")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #FF5924;
                color: white;
                border: 1px solid #FF5924;
                border-radius: 16px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF8550;
                border-color: #FF8550;
            }
        """)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)
        
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E5EAF2;
                border-radius: 8px;
                background-color: #FFFFFF;
            }
            QTabBar::tab {
                background-color: #F5F7F9;
                border: 1px solid #E5EAF2;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 12px;
                color: #4A5465;
                font-weight: bold;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border-color: #E5EAF2;
                color: #FF5924;
            }
            QLineEdit, QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 6px;
                padding: 6px 10px;
                color: #1A1C2E;
                font-size: 12px;
            }
            QLineEdit:hover, QTextEdit:hover {
                border-color: #FF8550;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #FF5924;
            }
            QSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF2;
                border-radius: 6px;
                padding: 3px 5px;
                color: #1A1C2E;
                font-size: 12px;
                min-height: 28px;
            }
            QSpinBox QLineEdit {
                background-color: transparent;
                color: #1A1C2E;
                border: none;
                padding: 0px;
                font-size: 12px;
            }
            QSpinBox:hover {
                border-color: #FF8550;
            }
            QSpinBox:focus {
                border-color: #FF5924;
            }
        """)
        
    def on_search_clicked(self):
        keyword = self.txt_keyword.text().strip()
        if keyword:
            self.search_requested.emit(keyword, self.spin_page.value())
            
    def set_search_loading(self, loading: bool):
        self.btn_search.setEnabled(not loading)
        if loading:
            self.lbl_search_status.setText("正在搜索中，请稍候...")
            self.lbl_search_status.setStyleSheet("color: #748297; font-weight: normal; background-color: transparent;")
        else:
            self.lbl_search_status.setStyleSheet("color: #FF5924; font-weight: bold; background-color: transparent;")
            
    def add_searched_codes(self, codes: list):
        if not codes:
            self.lbl_search_status.setText("未搜索到任何番号。")
            self.lbl_search_status.setStyleSheet("color: #FF453A; font-weight: bold; background-color: transparent;")
            return
            
        current_text = self.txt_codes.toPlainText().strip()
        codes_text = "\n".join(codes)
        if current_text:
            new_text = f"{current_text}\n{codes_text}"
        else:
            new_text = codes_text
            
        self.txt_codes.setText(new_text)
        self.lbl_search_status.setText(f"成功搜索并导入 {len(codes)} 个番号！已自动合并追加到贴入选项中。")
        self.lbl_search_status.setStyleSheet("color: #34C759; font-weight: bold; background-color: transparent;")
        
        # 自动切回到贴入标签，方便用户审阅与二次编辑
        self.tabs.setCurrentIndex(0)
        
    def get_entered_codes(self) -> list:
        import re
        raw_text = self.txt_codes.toPlainText().strip()
        if not raw_text:
            return []
            
        # 提取以换行、逗号、分号、空格分割的所有独立番号字符
        tokens = re.split(r'[,\s;，；\n]+', raw_text)
        valid_codes = []
        for t in tokens:
            cleaned = t.strip().upper()
            if cleaned:
                valid_codes.append(cleaned)
        return valid_codes
