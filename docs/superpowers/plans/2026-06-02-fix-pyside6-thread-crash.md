# PySide6 Thread Crash Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve PySide6 background thread deallocation crash (SIGSEGV) in QRunnable wrapper garbage collection by implementing main-thread garbage collection.

**Architecture:** Disable `QRunnable` auto-delete (`setAutoDelete(False)`), keep references to active workers in a strong set `self.active_workers` inside the `Controller` class, and delete/discard references on the main thread inside slot triggered by `finished_worker` signals emitted inside a `finally` block of both `ScrapeWorker` and `ImageLoadWorker`.

**Tech Stack:** Python 3, PySide6, Pytest

---

### Task 1: ScrapeWorker 异常保障重构与测试 (TDD)

**Files:**
- Modify: `gui/scrape_worker.py`
- Modify: `test/test_scrape_worker.py`

- [ ] **Step 1.1: 编写单元测试验证 finished_worker 信号的发射**
  在 `test/test_scrape_worker.py` 中，编写测试验证普通刮削与虚拟番号刮削任务均会在结束时无条件发射 `finished_worker` 信号并传递 `self`。
- [ ] **Step 1.2: 运行测试确保其失败**
  运行 `python3 -m pytest test/test_scrape_worker.py -v` 并确保失败（属性不存在或信号未定义）。
- [ ] **Step 1.3: 重构 `gui/scrape_worker.py`**
  在 `WorkerSignals` 中新增 `finished_worker = Signal(object)`，并将 `run` 的实现包入 `try-finally` 结构，确保最末尾无条件发射 `self.signals.finished_worker.emit(self)`。
- [ ] **Step 1.4: 再次运行测试确保其通过**
  运行 `python3 -m pytest test/test_scrape_worker.py -v` 确保 PASS。
- [ ] **Step 1.5: Git commit**
  ```bash
  git add gui/scrape_worker.py test/test_scrape_worker.py
  git commit -m "test & feat: implement finished_worker signal and try-finally guarantee for ScrapeWorker"
  ```

---

### Task 2: ImageLoadWorker 异常保障重构与测试 (TDD)

**Files:**
- Modify: `gui/controller.py`
- Create: `test/test_crash_prevention.py`

- [ ] **Step 2.1: 编写 ImageLoadWorker 的失败测试**
  在 `test/test_crash_prevention.py` 中，编写测试验证 `ImageLoadWorker` 结束时发射 `finished_worker` 信号传递自身。
- [ ] **Step 2.2: 运行测试确保失败**
  运行 `python3 -m pytest test/test_crash_prevention.py -v` 验证失败。
- [ ] **Step 2.3: 重构 `ImageLoadWorker`**
  在 `ImageLoadSignals` 中新增 `finished_worker = Signal(object)`，重构 `ImageLoadWorker.run` 为 `try-finally` 结构无条件发射该信号。
- [ ] **Step 2.4: 再次运行测试确保通过**
  运行 `python3 -m pytest test/test_crash_prevention.py -v` 确认 PASS。
- [ ] **Step 2.5: Git commit**
  ```bash
  git add gui/controller.py test/test_crash_prevention.py
  git commit -m "test & feat: implement finished_worker signal and try-finally guarantee for ImageLoadWorker"
  ```

---

### Task 3: 改造 Controller 实现 Worker 主线程管理及安全回收

**Files:**
- Modify: `gui/controller.py`

- [ ] **Step 3.1: 初始化活跃 Worker 集合并实现回收槽**
  在 `Controller.__init__` 中新增 `self.active_workers = set()`，并定义新方法 `on_worker_destroyed(self, worker)` 移除该引用。
- [ ] **Step 3.2: 接管所有 ScrapeWorker 和 ImageLoadWorker 启动**
  将 `gui/controller.py` 中所有启动 Worker 的 5 处地方修改为：设置 `setAutoDelete(False)`，连接 `finished_worker` 信号至 `on_worker_destroyed`，并把 Worker 加入 `self.active_workers` 中。
- [ ] **Step 3.3: 运行所有单元测试**
  运行 `python3 -m pytest -v` 确认所有 6 个单元测试完全通过。
- [ ] **Step 3.4: Git commit**
  ```bash
  git add gui/controller.py
  git commit -m "feat: manage and deallocate QRunnable wrappers safely on GUI main thread to prevent thread crash"
  ```
