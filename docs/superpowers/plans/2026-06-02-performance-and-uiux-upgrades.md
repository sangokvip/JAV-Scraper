# Performance and UI/UX Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement table cell QProgressBar injection for dynamic progress tracking, an elegant Empty State placeholder screen, automatic JSON backup persistence for tasks, Path Traversal safety validation, and HTTP Session connection reuse for fast image downloading. Omit Cookie encryption and masking.

**Architecture:** 
- Decouple task load/save logic to a new module `task_persister.py`.
- Handle Empty State dynamic visibility in `MainWindow` inside layouts.
- Parse progress ratios (e.g., `(10/30)`) inside `on_worker_progress` in `Controller` and dynamically set `QProgressBar` using `table.setCellWidget()`.
- Add Path Traversal checks inside `ScrapeWorker.run` before writing or creating any directories.
- Share a global `requests.Session` inside `ImageLoadWorker` to keep connection keep-alive.

**Tech Stack:** Python 3, PySide6, Pytest

---

### Task 1: Task Queue Persistence 模块与测试 (TDD)

**Files:**
- Create: `gui/task_persister.py`
- Create: `test/test_task_persister.py`

- [ ] **Step 1.1: 编写 task_persister 的单元测试**
  在 `test/test_task_persister.py` 中，编写保存和载入任务列表的测试用例。
- [ ] **Step 1.2: 运行测试确保失败**
  运行 `python3 -m pytest test/test_task_persister.py -v` 并验证失败。
- [ ] **Step 1.3: 实现 `gui/task_persister.py`**
  使用 JSON 格式将任务序列化写入本地 `tasks_backup.json`，支持保存和载入。
- [ ] **Step 1.4: 再次运行测试确保通过**
  运行 `python3 -m pytest test/test_task_persister.py -v` 并验证 PASS。
- [ ] **Step 1.5: Git commit**
  ```bash
  git add gui/task_persister.py test/test_task_persister.py
  git commit -m "test & feat: implement JSON task state persistence helper with tests"
  ```

---

### Task 2: 路径安全防穿越校验与测试 (TDD)

**Files:**
- Modify: `gui/scrape_worker.py`
- Create: `test/test_path_safety.py`

- [ ] **Step 2.1: 编写路径防隔离测试**
  在 `test/test_path_safety.py` 中编写用 `../` 等测试穿越路径，验证安全拦截功能。
- [ ] **Step 2.2: 运行测试确保失败**
  运行 `python3 -m pytest test/test_path_safety.py -v` 并验证失败。
- [ ] **Step 2.3: 修改 `gui/scrape_worker.py` 的落盘部分**
  在拼装文件夹和重命名视频前，使用 `os.path.abspath` 对目标路径做起始前缀判断，如果跳出了 output_dir 则抛出 PermissionError 终止任务。
- [ ] **Step 2.4: 再次运行测试确保通过**
  运行 `python3 -m pytest test/test_path_safety.py -v` 验证 PASS。
- [ ] **Step 2.5: Git commit**
  ```bash
  git add gui/scrape_worker.py test/test_path_safety.py
  git commit -m "test & feat: implement path traversal safety constraints in ScrapeWorker"
  ```

---

### Task 3: 改造 MainWindow 实现 Empty State 优雅占位与微动

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 3.1: 主窗口添加占位符控件**
  在 `MainWindow.init_ui` 中，添加一个精美高对比度的 QLabel `self.empty_placeholder` 并进行样式化（支持金色渐变文字和精美框线），覆盖在表格区域之上。
- [ ] **Step 3.2: 实现占位符的显隐切换函数**
  在 `MainWindow` 中实现 `update_empty_placeholder_visibility(self, is_empty: bool)`，控制占位符与表格的淡入淡出显示。
- [ ] **Step 3.3: 联动 hover 微光动效**
  在 stylesheet 中增强拖拽区和按钮的 transition transition-delay 及金色阴影过渡特效。
- [ ] **Step 3.4: Git commit**
  ```bash
  git add gui/main_window.py
  git commit -m "feat: add beautiful empty state placeholder screen and hover transition micro-animations"
  ```

---

### Task 4: 改造 Controller 实现任务恢复、图片 Session 共享及拟物 QProgressBar 注入

**Files:**
- Modify: `gui/controller.py`

- [ ] **Step 4.1: 在启动时载入并恢复历史备份任务，每次状态改变触发自动备份**
  在 `Controller.__init__` 中调用持久化辅助模块，从备份还原历史任务并在表格中重建行；在各个状态信号槽和清空移除方法尾部增加自动备份保存。
- [ ] **Step 4.2: 动态解析并注入拟物进度条**
  在 `on_worker_progress` 槽中，提取进度比率（如 `(10/35)` 结构），如果是，则在当前单元格动态嵌入暗金/深灰颜色的 `QProgressBar` 扁平进度条。在任务完成时将进度条移除恢复为优雅的 ✅ 文字。
- [ ] **Step 4.3: 共享全局 Requests.Session 并完成测试验证**
  在 `Controller` 类中定义 `self.image_session = requests.Session()` 并传递给 `ImageLoadWorker`，复用 TCP 长连接提升图片拉取速度。
- [ ] **Step 4.4: 运行所有单元测试**
  运行 `python3 -m pytest -v` 并确保全部测试通过。
- [ ] **Step 4.5: Git commit**
  ```bash
  git add gui/controller.py
  git commit -m "feat: implement JSON task restore, Keep-Alive sessions, and dynamic table QProgressBar injection"
  ```
