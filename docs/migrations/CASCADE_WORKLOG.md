# Cascade Worklog

所有代码与文档变动均记录在此，以保持上下文的连续性。

### 1) Chore: 初始化设计规范文档
- **变更文件**: `docs/superpowers/specs/2026-06-02-javdb-api-scraper-gui-design.md`, `docs/migrations/CASCADE_WORKLOG.md`
- **背景与目标**: 为项目编写支持 Win/Mac 双平台的 PySide6 GUI 软件的技术与视觉设计规范，确保后续实现有据可查。
- **技术实施**:
  - 创建并编写了 `docs/superpowers/specs/2026-06-02-javdb-api-scraper-gui-design.md` 规范。
- **风险自查**:
  - 属于新增文档，对已有爬虫 API 无任何 breaking changes。
- **回滚点**: 无需回滚。

### 2) Chore: 初始化实施计划文档
- **变更文件**: `docs/superpowers/plans/2026-06-02-javdb-api-scraper-gui.md`, `docs/migrations/CASCADE_WORKLOG.md`
- **背景与目标**: 详细梳理并划分开发阶段任务，确保按照 TDD (测试驱动开发) 的微颗粒度实现代码，无任何功能占位符，为实施阶段提供清晰步骤。
- **技术实施**:
  - 创建并编写了 `docs/superpowers/plans/2026-06-02-javdb-api-scraper-gui.md` 详细开发计划。
- **风险自查**:
  - 仅新增计划文档，无任何代码级改动，无 breaking changes。
- **回滚点**: 无需回滚。

### 3) Feature: 实现番号提取算法 (Code Extractor)
- **变更文件**: `lib/code_extractor.py`, `test/test_code_extractor.py`
- **背景与目标**: 实现从任意视频文件名中自动识别提取番号的核心算法，支持标准格式、FC2-PPV、T28以及无横杠格式清洗转换。
- **技术实施**:
  - 创建并实现 `lib/code_extractor.py` 番号提取逻辑。
  - 创建 `test/test_code_extractor.py` pytest 单元测试并验证全部通过。
- **风险自查**:
  - 为全新模块，不影响任何已有 scraper 功能。
- **回滚点**: `git reset --hard 6924cd0`

### 4) Feature: 实现 NFO 生成器 (NFO Generator)
- **变更文件**: `lib/nfo_generator.py`, `test/test_nfo_generator.py`
- **背景与目标**: 提供在本地生成与 Emby/Jellyfin 兼容的 `.nfo` 元数据 XML 描述文件的功能，便于播放器自动渲染信息。
- **技术实施**:
  - 创建并实现 `lib/nfo_generator.py`，输出标准的 XML 元素。
  - 创建 `test/test_nfo_generator.py` 自动化测试并成功验证各标签节点内容。
- **风险自查**:
  - 对已有 scraper 无任何副作用。
- **回滚点**: `git reset --hard 07507d2`

### 5) Feature: 支持代理配置传递到底层网络请求
- **变更文件**: `javdb_api.py`, `lib/javdb_adapter.py`, `lib/javbus_adapter.py`
- **背景与目标**: 提供在 API 会话和图片下载器中全局生效代理设置的能力，确保在受限网络环境下也能正常刮削。
- **技术实施**:
  - 在 `JavdbAPI.__init__` 中接受 `proxies` 字典并应用给 `self.session.proxies`。
  - 在 `JavdbAdapter.__init__` 接受代理参数，并在图片下载时将其传给 `requests.get`。
  - 在 `JavbusAdapter.__init__` 中兼容处理 dict 格式的代理输入。
- **风险自查**:
  - 可选参数 `proxies` 不传时默认为 None，完全向下兼容。
- **回滚点**: `git reset --hard e7179e2`

### 6) Feature: 实现异步后台刮削整理 Worker
- **变更文件**: `gui/scrape_worker.py`
- **背景与目标**: 提供在独立线程中执行刮削、图片下载、NFO 写入与文件整理重命名的异步任务。避免在网络请求和磁盘 I/O 阻塞 UI 界面。
- **技术实施**:
  - 创建 `gui/scrape_worker.py`，继承自 `QRunnable`。
  - 使用 Qt 信号系统（Signal/Slot）传递工作进度与最终状态。
  - 自动创建 Emby 风格目录，下载剧照到 `extrafanart/` 下。
- **风险自查**:
  - 新增类，独立线程执行，无 UI 主线程冲突风险。
- **回滚点**: `git reset --hard 7ab6990`

### 7) Feature: 实现主界面 View (MainWindow)
- **变更文件**: `gui/main_window.py`
- **背景与目标**: 基于 PySide6 构建高级白金黑杂志风的软件界面，包含左侧配置栏、中部任务管理区、右侧多媒体预览卡片，并全面支持文件与文件夹的鼠标拖入事件。
- **技术实施**:
  - 创建 `gui/main_window.py`。
  - 编写自定义 QSS 样式表，实现暗黑哑光黑背景、金色按钮高亮及各种控件的现代化扁平微圆角渲染。
  - 实现拖入事件代理 `files_dropped` 信号的抛出。
- **风险自查**:
  - UI 布局完全由局部组件构成，不干扰爬虫后端，无影响。
- **回滚点**: `git reset --hard 11587f8`

### 8) Feature: 实现 GUI 控制器 (Controller) 与业务调度
- **变更文件**: `gui/controller.py`
- **背景与目标**: 提供事件流绑定、任务列表状态同步更新、右侧多媒体数据预览（根据状态分别进行网络图预览或本地落盘图预览）以及代理与 Cookie 的动态保存/测试支持。
- **技术实施**:
  - 创建 `gui/controller.py`。
  - 使用 Qt 线程池限制并发数为 2，启动并绑定 `ScrapeWorker`。
  - 提供代理连通性 HTTP 快速测试逻辑与 JAVDB 的 `cookies.json` 本地解析持久化。
- **风险自查**:
  - 本模块作为中央控制器，不影响独立的原有命令式 scraper 功能。
- **回滚点**: `git reset --hard f0a902c`

### 9) Chore: 实现启动脚本并运行测试
- **变更文件**: `main.py`
- **背景与目标**: 提供项目的统一应用启动入口，加载 Qt 事件循环并展现 GUI 窗口。
- **技术实施**:
  - 创建启动脚本 `main.py`，完成 `QApplication` 的拉起、`MainWindow` 和 `Controller` 的实例化和关联。
  - 运行并通过了 `test_code_extractor.py` 和 `test_nfo_generator.py` 的所有测试。
- **风险自查**:
  - 作为入口脚本，安全无副作用。
- **回滚点**: `git reset --hard d53fa50`

### 10) Fix: 修复 QPushButton 信号槽绑定的连接参数错误
- **变更文件**: `gui/controller.py`
- **背景与目标**: 修复启动时报的 `TypeError: PySide6.QtCore.QObject.connect(): not enough arguments` 错误。
- **技术实施**:
  - 在 `Controller.__init__` 中，将直接对按钮 `connect` 修改为对按钮的 `clicked` 信号执行 `connect`，修正了信号绑定的标准 PySide6 写法。
- **风险自查**:
  - 已验证消除了启动异常。
- **回滚点**: `git reset --hard 1ab6627`

### 11) Fix: 优化代理测试算法，处理 Cloudflare 的 403 阻断
- **变更文件**: `gui/controller.py`
- **背景与目标**: 解决直接测试 `javdb.com` 会被 Cloudflare 拦截返回 403 并判定为测试失败的问题，实际上代理网络本身是通畅的。
- **技术实施**:
  - 先尝试请求 `www.google.com` 校验代理是否通畅。
  - 请求 `javdb.com` 时加入浏览器 UA 报头，并容包 403 状态码作为物理畅通的依据。
- **风险自查**:
  - 优化测试交互，无核心业务风险。
- **回滚点**: `git reset --hard 1e75ff4`

### 12) Fix & Feature: 修复按钮失效、添加手动刮削、磁力链接与剧照多图双击放大预览
- **变更文件**: `gui/main_window.py`, `gui/controller.py`, `gui/scrape_worker.py`
- **背景与目标**: 修复手动导入无反应的问题；支持手动添加番号以对无视频的任务进行整理和预览；展示影片磁力链接并以多线程异步展示剧照、支持双击弹窗放大。
- **技术实施**:
  - 修复 `import_files_manually` 和 `import_dir_manually` 被 `QPushButton.clicked` 触发时由于隐式参数 `checked` 而引发槽函数参数不匹配的 `TypeError`。
  - 主界面新增“手动输入番号...”按钮，控制器中实现 `add_code_manually` 创建 `__virtual__:番号` 任务，自动通过 `os.path.exists` 跳过视频物理移动，只刮削元数据、下载海报和剧照。
  - 右侧多媒体面板新增可滚动只读的磁力链接展示文本区。
  - 引入 `ImageLoadWorker` 在后台多线程异步依次拉取剧照网络图并用 `self.current_preview_filepath` 过滤切歌串色，彻底消除大图载入导致的 UI 冻结和错乱问题。
  - 支持直接读取落盘在本地的 `extrafanart/` 剧照文件；剧照均绑定双击事件至 `show_zoomed_image` 方法，采用 `PhotoDialog` 进行 800x600 居中弹窗展示。
- **风险自查**:
  - 虚拟任务自动在后台线程处理，对本地视频移动有安全校验。测试用例 100% 通过。
- **回滚点**: `git reset --hard 1e75ff4`

### 13) Fix & Feature: 重构磁力复制表格、添加自定义代理勾选联动及剧照单击放大
- **变更文件**: `gui/main_window.py`, `gui/controller.py`
- **背景与目标**: 优化磁力复制体验；兼容系统代理/TUN网卡拦截模式；修复并优化剧照放大功能。
- **技术实施**:
  - 将右侧详情多行磁力文本框重构为两列的 `QTableWidget` 磁力表格（大小、操作），点击“复制”按钮即可通过 `copy_to_clipboard` 方法自动写入系统剪贴板并弹出友好提醒，显著提升可读性。
  - 新增“启用自定义代理”复选框，默认不开启（输入框和测试按钮置灰），不勾选时在 `start_scraping` 和 `start_organizing` 中强制将 proxies 置为 `None`，完美走默认的系统代理/TUN网卡物理模式。
  - 将 `ClickableLabel` 里的 `mouseDoubleClickEvent` 重载为更敏捷的 `mousePressEvent` 单击判定，将 `double_clicked` 信号更改为 `clicked`，实现剧照**单击即放大**，解决 macOS 双击焦点判定问题。
- **风险自查**:
  - 重构对原核心刮削整理流程没有任何破坏性变动，测试用例 100% 通过。
- **回滚点**: `git reset --hard 21334ae`

### 14) Fix: 修复网络拉取海报和剧照时不尊重代理 CheckBox 开关状态的 Bug
- **变更文件**: `gui/controller.py`
- **背景与目标**: 修复已刮削未整理的影片在加载右侧海报与剧照时，由于直接无条件读取输入框中的默认端口而导致请求报错超时，从而无法显示图片的问题。
- **技术实施**:
  - 在 `show_preview_details` 方法中的网络海报拉取和剧照 `ImageLoadWorker` 启动时，均加入 `self.view.chk_custom_proxy.isChecked()` 的判断。当不勾选自定义代理时，一律强制将 proxies 设为 `None`，使其正常走默认的系统代理（TUN模式网卡）。
- **风险自查**:
  - 此修复仅针对 Controller 右侧看板加载阶段的代理逻辑，完全不影响其余爬虫抓取与文件处理核心层，安全可靠。
- **回滚点**: `git reset --hard bc17a06`

### 15) Fix: 修复 gui/controller.py 遗漏导入 QPushButton 的 NameError Bug
- **变更文件**: `gui/controller.py`
- **背景与目标**: 解决渲染磁力链接表格时，因遗漏导入 `QPushButton` 导致后台抛出 `NameError: name 'QPushButton' is not defined` 异常，进而引起后面海报和剧照加载被截断无法渲染的问题。
- **技术实施**:
  - 在 `gui/controller.py` 顶部的 `QtWidgets` 导入列表中补充引入 `QPushButton`。
- **风险自查**:
  - 补充导入操作，安全无风险。
- **回滚点**: `git reset --hard 562401b`

### 16) Fix & Feature: 隐藏垂直行号表头、美化 QMessageBox 暗黑样式并添加已完成任务重新刮削/整理提示
- **变更文件**: `gui/main_window.py`, `gui/controller.py`
- **背景与目标**: 隐藏界面上不美观的白色垂直表头；解决弹出对话框对比度低的问题；优化已刮削/已整理成功影片再次点击时的提示与重试体验。
- **技术实施**:
  - 隐藏主表格的垂直表头，根除最左侧系统默认渲染的纯白色长条。
  - 在 QSS 中为 `QMessageBox`, `QDialog`, `QInputDialog` 及其文字与按钮统一编写暗黑白金风格覆写，让弹出窗口以极具质感的黑底白字高对比度展现。
  - 重构 `start_scraping` 和 `start_organizing`：当检测到列表中不存在新任务，而均是已刮削/已整理的影片时，弹窗询问用户是否重新执行。若用户选择“是”，则将这些任务重设并加入运行队列，极大地优化了用户的重复刮削和整理调试体验。
- **风险自查**:
  - 对已有文件搬运与 NFO 流程完全兼容，没有破坏任何核心层，测试用例 100% 通过。
- **回滚点**: `git reset --hard ea6a0d5`

### 17) Fix & Feature: 修复单元格编辑高度挤压、预览弹窗缩水折拢、磁力三列高精度排序并实现手动添加番号后自动刮削
- **变更文件**: `gui/main_window.py`, `gui/controller.py`
- **背景与目标**: 修复双击修改番号时文字显示不清的 Bug；支持磁力列表按大小与日期物理双向排序并提取分享日期；修复剧照放大预览在 macOS 上折拢成窄缝的 Bug；提供手动添加番号后自动开始刮削而不需要二次点击的顺畅流体验。
- **技术实施**:
  - 在 `gui/main_window.py` 样式表中增加 `QTableWidget QLineEdit` 的 CSS 规则，消除 padding 使文字完整居中。
  - 将 `self.table_magnet` 扩展为 3 列（大小、日期、操作），启用表头排序并在 controller 填充时进行排序开启/关闭锁定。
  - 在 `gui/controller.py` 新增 `SortableTableWidgetItem`，自定义 `__lt__` 以根据数值（大小）和日期先后进行物理排序，而非显示文字字母序排序。
  - 在 `PhotoDialog` 初始化中计算 scaled_pixmap 大小，显式调用 `setFixedSize(w, h)` 以完美撑开弹窗。
  - 在 `add_code_manually` 方法尾部自动选中新增的任务行，并自动创建并启动 `ScrapeWorker` 任务。
- **风险自查**:
  - 所有改动完全基于 GUI 视图交互层与样式层，经 pytest 运行 100% 成功，未对底层爬虫元数据提取造成 breaking changes。
- **回滚点**: `git reset --hard 2a9e3bc`

### 18) Fix: 恢复剧照弹窗标题栏与关闭红绿灯按钮，并支持点击大图任意处即时关闭
- **变更文件**: `gui/controller.py`
- **背景与目标**: 修复大图放大弹窗遮挡主窗口且没有关闭按钮导致无法关闭的问题，并赋予其更快捷舒适的交互操作。
- **技术实施**:
  - 移除了 `PhotoDialog` 中的 `self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint)` 语句，恢复 macOS 系统自带的窗口修饰标题栏及红绿灯关闭按钮。
  - 在 `PhotoDialog` 类中重载了 `mousePressEvent` 事件，调用 `self.accept()`，使用户只需在图片的任意位置轻点鼠标即可瞬间退出预览，极大地方便了使用。
- **风险自查**:
  - 仅涉及预览弹窗的窗口配置及事件捕获，不影响任何业务模型与主数据流，安全可靠。
- **回滚点**: `git reset --hard eedf4f8`

### 19) Feature: 预览大图弹窗支持左右切换按钮、页码指示及键盘左右方向键切换
- **变更文件**: `gui/controller.py`
- **背景与目标**: 满足用户在剧照放大弹窗中通过左右按键及键盘方向键快捷选择并轮播查看下一张或上一张剧照的需求。
- **技术实施**:
  - 重构 `ClickableLabel` 的点击信号，改为传出自身 `QLabel` 引用。
  - 在 `Controller.show_zoomed_image` 中，通过扫描 `samples_layout` 容器下所有的剧照控件，提取全部无损图片对象并精确确定当前选中的剧照索引值 `current_index`。
  - 重构 `PhotoDialog` 接收当前的剧照 `pixmaps` 列表，使用 `QHBoxLayout` 在图片左右两侧插入半透明金色高亮悬浮感的 “◀” 和 “▶” 圆角切图按钮，在底部增加“剧照预览：X / Y”的金黄色页码文字。
  - 重载 `PhotoDialog.keyPressEvent`，捕获并处理 `Key_Left` 和 `Key_Right` 事件，实现键盘物理按键切换。
  - 优化大图点击关闭的触发逻辑，精确限定只在用户点击正中央 `lbl_image` 时才关闭弹窗，规避按钮和周边空白处的误触。
- **风险自查**:
  - 完全重构了弹窗内的内部逻辑，经 pytest 运行 100% 成功，没有破坏任何核心 scraper API 业务流，无 breaking changes。
- **回滚点**: `git reset --hard aabced6`
