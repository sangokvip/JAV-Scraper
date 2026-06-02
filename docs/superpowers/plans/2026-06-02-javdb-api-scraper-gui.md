# JAVDB API Scraper GUI 软件实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 PySide6 构建一个 Windows & Mac 双版本 GUI，支持文件拖入、自动识别番号、代理配置、Cookie 导入，并实现符合 Emby/Kodi 兼容海报墙规范的影片重命名整理与 XML 格式元数据 (NFO) 生成。

**Architecture:** 采用 MVVM 架构，主 UI 线程通过线程池 `QThreadPool` 与 `QRunnable` 启动异步后台刮削任务，避免阻塞界面；通过 Qt 的信号槽（Signals & Slots）异步传回海报路径和状态并刷新界面；网络请求层在底层 session 注入全局代理配置。

**Tech Stack:** Python 3, PySide6, pytest, curl_cffi, requests, lxml

---

### Task 1: 编写并验证番号提取算法 (Code Extractor)

**Files:**
- Create: `lib/code_extractor.py`
- Test: `test/test_code_extractor.py`

- [ ] **Step 1: 编写测试用例**
  创建 `test/test_code_extractor.py` 并写入：
  ```python
  import pytest
  from lib.code_extractor import extract_code

  def test_extract_code():
      # 标准有横杠
      assert extract_code("[1080p]SSIS-123_ch.mp4") == "SSIS-123"
      # 无横杠自动补横杠并转大写
      assert extract_code("ipx099.mkv") == "IPX-099"
      # FC2 特殊前缀
      assert extract_code("FC2-PPV-1234567.mp4") == "FC2-PPV-1234567"
      # 孤立数字不匹配
      assert extract_code("123.mp4") is None
      # 匹配不到返回 None
      assert extract_code("random_filename_without_code.mp4") is None
  ```

- [ ] **Step 2: 运行测试验证其失败**
  运行命令：
  ```bash
  pytest test/test_code_extractor.py
  ```
  预期结果：测试失败，提示 `ModuleNotFoundError: No module named 'lib.code_extractor'`。

- [ ] **Step 3: 编写最小实现代码**
  创建 `lib/code_extractor.py` 并写入：
  ```python
  import re

  def extract_code(filename: str) -> str:
      # 1. 预清洗：移除常见无码/字幕标识
      clean_name = re.sub(r'(?i)\[(1080p|720p|8k|4k|hhd|hd|中文字幕|字幕)\]', '', filename)
      clean_name = re.sub(r'(?i)[-_](ch|c|uncensored|diy)\b', '', clean_name)
      
      # 2. 匹配 FC2 PPV
      fc2_match = re.search(r'(?i)\bfc2[-_]?ppv[-_]?(\d{5,7})\b', clean_name)
      if fc2_match:
          return f"FC2-PPV-{fc2_match.group(1)}"
          
      # 3. 匹配 T28
      t28_match = re.search(r'(?i)\bt28[-_]?(\d{3,4})\b', clean_name)
      if t28_match:
          return f"T28-{t28_match.group(1)}"

      # 4. 匹配标准 (字母)-(数字)
      std_match = re.search(r'(?i)\b([a-z]{2,5})[-_]?(\d{3,5})\b', clean_name)
      if std_match:
          prefix = std_match.group(1).upper()
          num = std_match.group(2)
          return f"{prefix}-{num}"
          
      return None
  ```

- [ ] **Step 4: 运行测试验证其通过**
  运行命令：
  ```bash
  pytest test/test_code_extractor.py
  ```
  预期结果：测试通过 (100% PASS)。

- [ ] **Step 5: 提交代码**
  运行命令：
  ```bash
  git add lib/code_extractor.py test/test_code_extractor.py
  git commit -m "feat: add code extractor and tests"
  ```

---

### Task 2: 编写并验证 NFO 生成器 (NFO Generator)

**Files:**
- Create: `lib/nfo_generator.py`
- Test: `test/test_nfo_generator.py`

- [ ] **Step 1: 编写 NFO 写入测试用例**
  创建 `test/test_nfo_generator.py` 并写入：
  ```python
  import os
  import xml.etree.ElementTree as ET
  from lib.nfo_generator import generate_nfo

  def test_generate_nfo(tmp_path):
      target_nfo = tmp_path / "test_movie.nfo"
      data = {
          "code": "SSIS-123",
          "title": "秘密のデート",
          "date": "2026-03-04",
          "studio": "S1 NO.1 STYLE",
          "tags": ["美少女", "单体"],
          "actors": ["井上もも"],
          "plot": "这里是剧情大纲。"
      }
      
      generate_nfo(data, str(target_nfo))
      
      assert target_nfo.exists()
      tree = ET.parse(target_nfo)
      root = tree.getroot()
      
      assert root.tag == "movie"
      assert root.find("title").text == "[SSIS-123] 秘密のデート"
      assert root.find("uniqueid").text == "SSIS-123"
      assert root.find("premiered").text == "2026-03-04"
      assert root.find("studio").text == "S1 NO.1 STYLE"
      genres = [g.text for g in root.findall("genre")]
      assert "美少女" in genres
      assert "单体" in genres
      actors = [a.find("name").text for a in root.findall("actor")]
      assert "井上もも" in actors
  ```

- [ ] **Step 2: 运行测试验证其失败**
  运行命令：
  ```bash
  pytest test/test_nfo_generator.py
  ```
  预期结果：测试失败，提示 `ModuleNotFoundError: No module named 'lib.nfo_generator'`。

- [ ] **Step 3: 编写最小实现代码**
  创建 `lib/nfo_generator.py` 并写入：
  ```python
  import xml.etree.ElementTree as ET
  import xml.dom.minidom as minidom

  def generate_nfo(data: dict, output_path: str):
      root = ET.Element("movie")
      
      # 标题
      title_val = f"[{data.get('code', '')}] {data.get('title', '')}"
      ET.SubElement(root, "title").text = title_val
      ET.SubElement(root, "originaltitle").text = data.get("title", "")
      
      # 番号 ID
      uniqueid = ET.SubElement(root, "uniqueid", type="num", default="true")
      uniqueid.text = data.get("code", "")
      
      # 发行日期
      ET.SubElement(root, "premiered").text = data.get("date", "")
      ET.SubElement(root, "releasedate").text = data.get("date", "")
      
      # 片商
      ET.SubElement(root, "studio").text = data.get("studio", "")
      
      # 标签
      for tag in data.get("tags", []):
          ET.SubElement(root, "genre").text = tag
          
      # 演员
      for actor_name in data.get("actors", []):
          actor_el = ET.SubElement(root, "actor")
          ET.SubElement(actor_el, "name").text = actor_name
          ET.SubElement(actor_el, "role").text = "Actor"
          
      # 简介
      ET.SubElement(root, "plot").text = data.get("plot", "")
      
      # 默认海报/背景图
      ET.SubElement(root, "poster").text = "poster.jpg"
      ET.SubElement(root, "fanart").text = "fanart.jpg"
      
      # 美化 XML 输出
      raw_xml = ET.tostring(root, encoding="utf-8")
      parsed = minidom.parseString(raw_xml)
      pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
      
      with open(output_path, "wb") as f:
          f.write(pretty_xml)
  ```

- [ ] **Step 4: 运行测试验证其通过**
  运行命令：
  ```bash
  pytest test/test_nfo_generator.py
  ```
  预期结果：测试通过 (100% PASS)。

- [ ] **Step 5: 提交代码**
  运行命令：
  ```bash
  git add lib/nfo_generator.py test/test_nfo_generator.py
  git commit -m "feat: add NFO generator and tests"
  ```

---

### Task 3: 适配代理到底层 scraper 请求中

**Files:**
- Modify: `javdb_api.py`
- Modify: `lib/javdb_adapter.py`
- Modify: `lib/javbus_adapter.py`

- [ ] **Step 1: 在 `javdb_api.py` 的 Session 中注入代理支持**
  在 `javdb_api.py` 的初始化中暴露 `proxies` 参数：
  修改 `javdb_api.py` 的 `__init__` 函数，允许接收 `proxies` 字典并应用给 `self.session.proxies`：
  ```python
  # 修改前 (大约 80 行附近)
  # self.session = requests.Session()
  # 修改后：
  # self.session = requests.Session()
  # if proxies:
  #     self.session.proxies = proxies
  ```
  并在 `lib/javdb_adapter.py` 和 `lib/javbus_adapter.py` 中的网络请求方法中，也将代理参数代入，尤其是下载图片时，把普通的 `requests.get` 修改为支持代理的请求，确保大封面下载在代理下有效：
  ```python
  # 在 lib/javdb_adapter.py 中修改 download_video_images
  # 修改为：
  # response = requests.get(img_url, timeout=30, proxies=self.proxies)
  ```

- [ ] **Step 2: 提交代理注入代码**
  运行命令：
  ```bash
  git add javdb_api.py lib/javdb_adapter.py lib/javbus_adapter.py
  git commit -m "feat: inject proxy settings into scraper session and image downloader"
  ```

---

### Task 4: 编写后台刮削与整理 Worker (ScrapeWorker)

**Files:**
- Create: `gui/scrape_worker.py`

- [ ] **Step 1: 编写异步 Worker 代码**
  创建 `gui/scrape_worker.py`，它继承 `QRunnable` 并在单独的线程中执行刮削、图片下载、元数据生成和文件搬运逻辑：
  ```python
  import os
  import shutil
  import traceback
  from PySide6.QtCore import QRunnable, QObject, Signal
  from lib import get_video_by_code
  from lib.nfo_generator import generate_nfo
  from lib.code_extractor import extract_code

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

              self.signals.progress.emit(self.file_path, "正在刮削元数据...")
              # 1. 调用已有的 API 获取数据
              detail = get_video_by_code(self.code, platform=self.platform)
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

              # 如果源文件和目标文件不同，则进行复制/移动
              if os.path.exists(self.file_path) and self.file_path != target_video_path:
                  shutil.move(self.file_path, target_video_path)

              # 4. 写入元数据 NFO
              self.signals.progress.emit(self.file_path, "正在生成元数据 NFO...")
              nfo_path = os.path.join(target_folder, f"{self.code}.nfo")
              # 构造适合 NFO 写入的元数据
              nfo_data = {
                  "code": self.code,
                  "title": detail.get("title", ""),
                  "date": detail.get("date", ""),
                  "studio": detail.get("series", "") or detail.get("maker", ""),
                  "tags": detail.get("tags", []),
                  "actors": detail.get("actors", []),
                  "plot": ""  # 可选：简介字段
              }
              generate_nfo(nfo_data, nfo_path)

              # 5. 下载海报大图 poster.jpg
              self.signals.progress.emit(self.file_path, "正在下载封面大图...")
              cover_url = detail.get("cover_url")
              if cover_url:
                  import requests
                  # 使用我们注入的代理下载
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
                      r = requests.get(img_url, timeout=30, proxies=self.proxies)
                      if r.status_code == 200:
                          img_path = os.path.join(extrafanart_dir, f"fanart{idx+1}.jpg")
                          with open(img_path, "wb") as f:
                              f.write(r.content)
                      self.signals.progress.emit(self.file_path, f"正在下载预览图 ({idx+1}/{len(thumbnails)})...")

              self.signals.finished.emit(self.file_path, "success")

          except Exception as e:
              traceback.print_exc()
              self.signals.finished.emit(self.file_path, f"刮削异常: {str(e)}")
  ```

- [ ] **Step 2: 提交 Worker 代码**
  运行命令：
  ```bash
  git add gui/scrape_worker.py
  git commit -m "feat: implement multi-threaded ScrapeWorker"
  ```

---

### Task 5: 编写主界面 View (MainWindow)

**Files:**
- Create: `gui/main_window.py`

- [ ] **Step 1: 编写 MainWindow 类**
  创建 `gui/main_window.py`，实现极简白金黑暗色风格的布局、拖拽接收以及各个交互板块：
  ```python
  import os
  from PySide6.QtWidgets import (
      QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTableWidget,
      QTableWidgetItem, QPushButton, QLabel, QLineEdit, QTextEdit,
      QFileDialog, QAbstractItemView, QHeaderView, QRadioButton, QButtonGroup
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
          self.proxy_input = QLineEdit("http://127.0.0.1:7890")
          self.proxy_input.setPlaceholderText("例如 http://127.0.0.1:7890")
          left_layout.addWidget(self.proxy_input)

          self.btn_test_proxy = QPushButton("测试代理连接")
          left_layout.addWidget(self.btn_test_proxy)
          self.lbl_proxy_status = QLabel("代理状态: 未测试")
          self.lbl_proxy_status.setObjectName("ProxyStatusLabel")
          left_layout.addWidget(self.lbl_proxy_status)

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
          center_layout.addWidget(self.table)

          # 操作按钮
          btn_layout = QHBoxLayout()
          self.btn_clear = QPushButton("一键清空")
          self.btn_clear.setObjectName("ClearBtn")
          self.btn_start = QPushButton("开始刮削并整理")
          self.btn_start.setObjectName("StartBtn")
          btn_layout.addWidget(self.btn_clear)
          btn_layout.addWidget(self.btn_start)
          center_layout.addLayout(btn_layout)

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
                  background-color: #D4AF37;
                  color: #121212;
                  border: none;
              }
              #StartBtn:hover {
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
  ```

- [ ] **Step 2: 提交 MainWindow 代码**
  运行命令：
  ```bash
  git add gui/main_window.py
  git commit -m "feat: implement MainWindow UI with custom stylesheet"
  ```

---

### Task 6: 编写 GUI 控制器 (Controller) 与业务调度

**Files:**
- Create: `gui/controller.py`

- [ ] **Step 1: 编写 Controller 代码**
  创建 `gui/controller.py`。其连接 UI 的各种动作，读取拖入的文件，触发正则番号匹配填充列表，并进行后台异步任务多线程派发：
  ```python
  import os
  from PySide6.QtCore import QThreadPool, Qt
  from PySide6.QtWidgets import QTableWidgetItem, QMessageBox
  from gui.main_window import MainWindow
  from gui.scrape_worker import ScrapeWorker
  from lib.code_extractor import extract_code

  class Controller:
      def __init__(self, view: MainWindow):
          self.view = view
          self.thread_pool = QThreadPool.globalInstance()
          # 限制并发，防止被 JAVDB 频繁屏蔽 IP
          self.thread_pool.setMaxThreadCount(2)
          
          # 存储当前列表文件的元数据： {filepath: {"code": str, "row": int}}
          self.task_files = {}

          # 初始化保存路径为本地 output 目录
          default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
          self.view.path_input.setText(default_out)

          # 绑定信号
          self.view.files_dropped.connect(self.handle_files_dropped)
          self.view.btn_browse.connect(self.browse_output_dir)
          self.view.btn_clear.connect(self.clear_all_tasks)
          self.view.btn_start.connect(self.start_scraping)
          self.view.btn_test_proxy.connect(self.test_proxy_connection)
          self.view.table.itemSelectionChanged.connect(self.handle_selection_changed)
          self.view.table.itemChanged.connect(self.handle_cell_changed)

      def handle_files_dropped(self, paths: list):
          # 提取所有支持的文件路径（如果是文件夹则扫描下面常见的视频格式）
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
                  continue # 避免重复导入

              # 自动提取番号
              code = extract_code(os.path.basename(file_path)) or ""
              
              row = self.view.table.rowCount()
              self.view.table.insertRow(row)

              # ID
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

              # 状态
              status_item = QTableWidgetItem("排队中" if code else "番号待补充")
              status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
              self.view.table.setItem(row, 3, status_item)

              self.task_files[file_path] = {
                  "code": code,
                  "row": row
              }

      def handle_cell_changed(self, item):
          # 当用户在表格修改番号时更新状态
          if item.column() == 2:
              row = item.row()
              # 查找对应的 file_path
              for fp, info in self.task_files.items():
                  if info["row"] == row:
                      new_code = item.text().strip()
                      info["code"] = new_code
                      status_item = self.view.table.item(row, 3)
                      if status_item:
                          status_item.setText("排队中" if new_code else "番号待补充")
                      break

      def browse_output_dir(self):
          dir_path = QFileDialog.getExistingDirectory(self.view, "选择输出文件夹")
          if dir_path:
              self.view.path_input.setText(os.path.abspath(dir_path))

      def clear_all_tasks(self):
          self.view.table.setRowCount(0)
          self.task_files.clear()
          self.view.lbl_cover.setText("选择影片以预览海报")
          self.view.lbl_cover.setPixmap(QPixmap())
          self.view.lbl_info_title.setText("影片番号与标题")
          self.view.lbl_info_details.setText("制片商: -\n发行日期: -\n演员: -")

      def test_proxy_connection(self):
          proxy = self.view.proxy_input.text().strip()
          self.view.lbl_proxy_status.setText("测试中...")
          
          # 定义一个简单的网络测试
          import requests
          proxies = {"http": proxy, "https": proxy} if proxy else None
          try:
              # 尝试连接 javdb.com，验证代理是否打通
              r = requests.get("https://javdb.com", timeout=10, proxies=proxies)
              if r.status_code == 200:
                  self.view.lbl_proxy_status.setText("连接正常 (OK)")
                  self.view.lbl_proxy_status.setStyleSheet("color: #34C759;") # 森林绿
              else:
                  self.view.lbl_proxy_status.setText(f"错误: 状态码 {r.status_code}")
                  self.view.lbl_proxy_status.setStyleSheet("color: #FF453A;")
          except Exception as e:
              self.view.lbl_proxy_status.setText("连接失败 (超时/不可用)")
              self.view.lbl_proxy_status.setStyleSheet("color: #FF453A;")

      def start_scraping(self):
          output_dir = self.view.path_input.text().strip()
          if not output_dir:
              QMessageBox.warning(self.view, "警告", "请先选择目标保存路径！")
              return

          proxy = self.view.proxy_input.text().strip()
          proxies = {"http": proxy, "https": proxy} if proxy else None
          platform = "javdb" if self.view.radio_javdb.isChecked() else "javbus"

          for file_path, info in list(self.task_files.items()):
              code = info["code"]
              row = info["row"]
              if not code:
                  continue

              # 创建异步工作任务
              worker = ScrapeWorker(file_path, code, output_dir, platform, proxies)
              worker.signals.started.connect(self.on_worker_started)
              worker.signals.progress.connect(self.on_worker_progress)
              worker.signals.preview_loaded.connect(self.on_worker_preview_loaded)
              worker.signals.finished.connect(self.on_worker_finished)

              self.thread_pool.start(worker)

      # 信号槽处理器
      def on_worker_started(self, filepath):
          row = self.task_files[filepath]["row"]
          self.view.table.setItem(row, 3, QTableWidgetItem("正在刮削..."))

      def on_worker_progress(self, filepath, message):
          row = self.task_files[filepath]["row"]
          self.view.table.setItem(row, 3, QTableWidgetItem(message))

      def on_worker_preview_loaded(self, filepath, detail):
          # 当后台抓取完成预览后，可以局部更新详情
          pass

      def on_worker_finished(self, filepath, status):
          row = self.task_files[filepath]["row"]
          if status == "success":
              self.view.table.setItem(row, 3, QTableWidgetItem("刮削成功"))
              # 从任务追踪中移除，防止重复执行
              self.task_files.pop(filepath, None)
          else:
              self.view.table.setItem(row, 3, QTableWidgetItem(f"失败: {status}"))

      def handle_selection_changed(self):
          # 处理列表中某行被选中时右侧预览的刷新
          selected_ranges = self.view.table.selectedRanges()
          if not selected_ranges:
              return
          row = selected_ranges[0].topRow()
          
          # 根据行号找到对应的 filepath
          filepath = None
          for fp, info in self.task_files.items():
              if info["row"] == row:
                  filepath = fp
                  break
          
          if not filepath:
              return

          # 如果是正在刮削成功或有临时详情，可以进行加载渲染
          # 暂时以基础展示为主
          self.view.lbl_info_title.setText(f"本地视频:\n{os.path.basename(filepath)}")
          self.view.lbl_info_details.setText(f"完整路径:\n{filepath}")
  ```

- [ ] **Step 2: 提交 Controller 代码**
  运行命令：
  ```bash
  git add gui/controller.py
  git commit -m "feat: implement Controller to coordinate model and view"
  ```

---

### Task 7: 编写启动脚本并运行测试

**Files:**
- Create: `main.py`

- [ ] **Step 1: 编写 main.py 启动脚本**
  在项目根目录下创建 `main.py`：
  ```python
  import sys
  from PySide6.QtWidgets import QApplication
  from gui.main_window import MainWindow
  from gui.controller import Controller

  def main():
      app = QApplication(sys.argv)
      window = MainWindow()
      controller = Controller(window)
      window.show()
      sys.exit(app.exec())

  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 2: 提交 main.py 脚本**
  运行命令：
  ```bash
  git add main.py
  git commit -m "feat: add application entry script main.py"
  ```

- [ ] **Step 3: 运行自动化测试检查各核心计算层正确性**
  运行命令：
  ```bash
  pytest test/test_code_extractor.py test/test_nfo_generator.py -v
  ```
  预期结果：全部测试通过，输出类似 `2 passed in ... seconds`。
