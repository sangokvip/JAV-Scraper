# JAV SCRAPER 界面样式定义 (Meadow 极奢暖白金视觉体系)

STYLE_SHEET = """
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
    QCheckBox {
        color: #1A1C2E;
        font-weight: 600;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1.5px solid #D4DCE5;
        border-radius: 4px;
        background-color: #FFFFFF;
    }
    QCheckBox::indicator:hover {
        border-color: #FF5924;
    }
    QCheckBox::indicator:checked {
        background-color: #FF5924;
        border-color: #FF5924;
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
        border: none;
        border-radius: 10px;
        padding: 5px 10px;
        font-size: 12px;
        font-weight: bold;
        min-width: 48px;
    }
    #CopyMagnetBtn:hover {
        background-color: #FF8550;
    }
    #CopyMagnetBtn:pressed {
        background-color: #E04414;
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
    /* 全局垂直滚动条美化 */
    QScrollBar:vertical {
        border: none;
        background-color: #F0F2F5;
        width: 8px;
        margin: 0px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background-color: #D4DCE5;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #FF5924;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        border: none;
        background: none;
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    /* 全局水平滚动条美化 */
    QScrollBar:horizontal {
        border: none;
        background-color: #F0F2F5;
        height: 8px;
        margin: 0px;
        border-radius: 4px;
    }
    QScrollBar::handle:horizontal {
        background-color: #D4DCE5;
        min-width: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:horizontal:hover {
        background-color: #FF5924;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        border: none;
        background: none;
        width: 0px;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;
    }

    /* 药丸状态过滤单选按钮样式 */
    QPushButton.PillFilter {
        background-color: #FFFFFF;
        border: 1.5px solid #E5EAF2;
        border-radius: 14px;
        padding: 4px 10px;
        color: #4A5465;
        font-size: 11px;
        font-weight: bold;
    }
    QPushButton.PillFilter:hover {
        background-color: #F5F7F9;
        border-color: #FF5924;
        color: #1A1C2E;
    }
    QPushButton.PillFilter:checked {
        background-color: #FF5924;
        border-color: #FF5924;
        color: #FFFFFF;
    }
"""
