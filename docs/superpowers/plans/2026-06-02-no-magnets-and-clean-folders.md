# No Magnets & Folder Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ignore magnets for imported videos, display original file path in card preview, and ask user to clean up empty source folders once migration completes.

**Architecture:** Block magnets inside `ScrapeWorker` by setting `detail["magnets"] = []` for non-virtual tasks. Display paths in `show_preview_details`. Decouple directory emptiness detection and path safety whitelist validation into a new helper module `folder_cleaner.py` for testing and hygiene purposes, integrated into `on_worker_finished`.

**Tech Stack:** Python 3, PySide6, Pytest

---

### Task 1: 创建 Folder Cleaner 模块与测试 (TDD)

**Files:**
- Create: `gui/folder_cleaner.py`
- Create: `test/test_folder_cleaner.py`

- [ ] **Step 1: 编写 folder_cleaner 的失败测试**
  在 `test/test_folder_cleaner.py` 中编写空目录识别、垃圾文件忽略和敏感目录拦截的单元测试。
- [ ] **Step 2: 运行测试并确保其失败**
  运行 `python3 -m pytest test/test_folder_cleaner.py -v` 并验证失败（文件不存在或方法未定义）。
- [ ] **Step 3: 实现 `gui/folder_cleaner.py`**
  实现 `clean_empty_parent_dirs` 逻辑与系统级敏感路径白名单校验。
- [ ] **Step 4: 再次运行测试确保其通过**
  运行 `python3 -m pytest test/test_folder_cleaner.py -v` 确保 PASS。
- [ ] **Step 5: Git commit**
  ```bash
  git add gui/folder_cleaner.py test/test_folder_cleaner.py
  git commit -m "test & feat: implement folder_cleaner helper with unit tests"
  ```

---

### Task 2: ScrapeWorker 屏蔽磁力逻辑与测试 (TDD)

**Files:**
- Modify: `gui/scrape_worker.py`
- Create: `test/test_scrape_worker.py`

- [ ] **Step 1: 编写 ScrapeWorker 过滤磁力的测试**
  在 `test/test_scrape_worker.py` 中，使用 MagicMock 和 patch 验证非 virtual 任务屏蔽磁力，virtual 任务保留磁力。
- [ ] **Step 2: 运行测试确保失败**
  运行 `python3 -m pytest test/test_scrape_worker.py -v` 并验证失败。
- [ ] **Step 3: 修改 `gui/scrape_worker.py`**
  在获取 `detail` 后，如果是普通文件，将 `detail["magnets"]` 置为空列表。
- [ ] **Step 4: 再次运行测试确保通过**
  运行 `python3 -m pytest test/test_scrape_worker.py -v` 确认 PASS。
- [ ] **Step 5: Git commit**
  ```bash
  git add gui/scrape_worker.py test/test_scrape_worker.py
  git commit -m "test & feat: filter magnets for non-virtual jobs in ScrapeWorker"
  ```

---

### Task 3: 改造 Controller 展现原文件路径及清理原文件夹

**Files:**
- Modify: `gui/controller.py`

- [ ] **Step 1: 引入 folder_cleaner，初始化处理目录集**
  在 `gui/controller.py` 头部导入 `clean_empty_parent_dirs`，并在 `__init__` 中加入 `self.processed_parent_dirs = set()`。
- [ ] **Step 2: 在详情看板显示原文件位置**
  修改 `show_preview_details`。若 `filepath` 不是 `__virtual__:` 前缀，拼装 details 字符串时追加 `原文件路径: {filepath}\n\n`。
- [ ] **Step 3: 汇总收集并盘点清理原文件夹**
  在 `on_worker_finished` 中当 `status == "success"` 且不以 `__virtual__:` 开头时收集 `os.path.dirname(filepath)`；在方法最后，若所有任务已结束，调用盘点程序获取可清理目录，并弹窗提示删除。
- [ ] **Step 4: 执行本地单元测试**
  运行 `python3 -m pytest -v` 确认全部测试通过。
- [ ] **Step 5: Git commit**
  ```bash
  git add gui/controller.py
  git commit -m "feat: show original file path and prompt for cleaning empty source folder on migration finish"
  ```
