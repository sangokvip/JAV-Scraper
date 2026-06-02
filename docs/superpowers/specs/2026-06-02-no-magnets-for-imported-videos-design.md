# 设计文档：导入影片默认屏蔽磁力链接刮削与展示 & 整理完询问清理原文件夹

## 背景与需求
目前，无论是手动输入番号产生的任务，还是拖入/导入本地影片产生的刮削任务，都会自动抓取并展示磁力链接。
用户希望：
1. **导入的影片文件**默认**不需要**刮削与展示磁力链接。
2. **只有**手动输入番号产生的任务（通常以 `__virtual__:` 为前缀）才允许刮削和展示磁力链接。
3. 在选择的影片卡片中，**显示其原文件位置**（方便用户查看和溯源）。
4. 本地视频整理完成后（视频移走），如果是批量任务，应该在**所有视频整理完成后询问是否删除变为空的原文件夹**。

---

## 方案对比

### 1. 屏蔽磁力链接刮削与展示
*   **方案 1 (推荐)**：在 `gui/scrape_worker.py` 的 `run` 线程中拦截。
    *   如果 `self.file_path` 不以 `__virtual__:` 开头，则强行将详情中的 `detail["magnets"]` 设为 `[]`。
    *   **理由**：改动小（`scrape_worker.py` 仅 147 行），源头阻断，UI 渲染层天然继承空数据，极其干净，且完全避开对 900+ 行的 `controller.py` 做复杂修改。

### 2. 显示原文件位置
*   在详情卡片面板渲染方法 `show_preview_details(detail, filepath, loaded_local)` 中，若 `filepath` 不以 `__virtual__:` 开头，则在 `info_details_text` 文字区域追加渲染一行 `原文件路径: {filepath}`。

### 3. 整理完成后询问是否删除原文件夹
*   **方案 A (推荐)**：**任务队列全部完成时汇总盘点并单次询问**。
    *   在控制器初始化时维护一个集合 `self.processed_parent_dirs = set()` 用于记录本次整理中发生移动的视频的直接父目录。
    *   每次单个任务以 `success` 状态结束时，如果其非虚拟任务，将 `os.path.dirname(filepath)` 加入集合。
    *   在每个任务结束时，遍历当前 `self.task_files` 的状态。若所有任务的 `status` 均不处于进行中状态（如“刮削中...”, “准备中” 等），表明本批次任务全部结束。
    *   此时，对收集到的原父目录进行盘点：
        1. 排除系统或用户敏感路径（如根目录、桌面、文档、下载、影片等，防止误删用户常用大目录）。
        2. 确认该目录在本地是否依然存在，且其内容除去 `.DS_Store` 或 `Thumbs.db` 等垃圾隐藏文件后是否已为空。
    *   若盘点后存在可删除的空原文件夹，则在主线程弹出**单个** `QMessageBox.question` 确认框询问用户是否进行清理，同意后调用 `shutil.rmtree` 统一删除。
    *   **理由**：用户体验极佳，避免了批量刮削时频繁弹窗骚扰。自带敏感目录过滤，安全性高。
*   **方案 B**：单个任务一整理完就弹窗询问。
    *   **缺点**：若有 20 个视频移动完成，会连续弹出 20 次确认框，体验灾难。

---

## 详细实施计划

### 修改文件
*   [gui/scrape_worker.py](file:///Users/mac/Documents/GitHub/%20javdb-api-scraper/gui/scrape_worker.py)
*   [gui/controller.py](file:///Users/mac/Documents/GitHub/%20javdb-api-scraper/gui/controller.py)

### 变更细节

#### 1. `gui/scrape_worker.py`
在 `run(self)` 方法中成功获取 `detail` 后、发送 `preview_loaded` 前（约第 53-56 行），增加：
```python
            # 若不是手动输入的虚拟任务，则将磁力列表置空，不刮削和显示磁力
            if not self.file_path.startswith("__virtual__:"):
                detail["magnets"] = []
```

#### 2. `gui/controller.py`
*   在 `__init__` 中新增：
    ```python
    self.processed_parent_dirs = set()
    ```
*   在 `show_preview_details` 中追加原文件路径展示：
    ```python
        info_details_text = (
            f"片商: {studio_str}\n"
            f"发行日期: {date_str}\n"
            f"演员: {actors_str}\n\n"
        )
        if not filepath.startswith("__virtual__:"):
            info_details_text += f"原文件路径: {filepath}\n\n"
            
        info_details_text += f"标签: {', '.join(detail.get('tags', []))}"
    ```
*   在 `on_worker_finished` 中，当 `status == "success"` 且 `not filepath.startswith("__virtual__:")` 时，添加：
    ```python
    parent_dir = os.path.dirname(filepath)
    self.processed_parent_dirs.add(parent_dir)
    ```
*   在 `on_worker_finished` 方法的最后，增加全局任务完成度判定和空文件夹清理逻辑：
    ```python
        # 检查是否所有任务都已执行完毕
        all_done = True
        for fp, t_info in self.task_files.items():
            if t_info.get("status") in ("刮削中...", "准备中", "正在移动与重命名影片...", "正在生成元数据 NFO...", "正在下载封面大图...", "正在下载预览图..."):
                all_done = False
                break
        
        if all_done and self.processed_parent_dirs:
            empty_dirs = []
            for pdir in self.processed_parent_dirs:
                if os.path.exists(pdir) and os.path.isdir(pdir):
                    try:
                        abs_pdir = os.path.abspath(pdir)
                        user_home = os.path.expanduser("~")
                        sensitive_paths = [
                            os.path.abspath(user_home),
                            os.path.abspath(os.path.join(user_home, "Desktop")),
                            os.path.abspath(os.path.join(user_home, "Documents")),
                            os.path.abspath(os.path.join(user_home, "Downloads")),
                            os.path.abspath(os.path.join(user_home, "Movies")),
                            os.path.abspath(os.path.join(user_home, "Pictures")),
                            os.path.abspath(os.path.join(user_home, "Music")),
                        ]
                        # 确保不是敏感文件夹且路径长度足够安全
                        if abs_pdir in sensitive_paths or len(abs_pdir) <= 10:
                            continue
                        
                        items = os.listdir(abs_pdir)
                        # 排除垃圾文件
                        remaining = [i for i in items if i not in (".DS_Store", "Thumbs.db")]
                        if not remaining:
                            empty_dirs.append(abs_pdir)
                    except Exception as e:
                        print(f"检查文件夹空状态失败 {pdir}: {e}")
            
            if empty_dirs:
                dir_list_str = "\n".join(empty_dirs)
                reply = QMessageBox.question(
                    self.view,
                    "清理空文件夹",
                    f"以下原视频所在的文件夹在整理后已变为空，是否删除它们？\n\n{dir_list_str}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    import shutil
                    for pdir in empty_dirs:
                        try:
                            shutil.rmtree(pdir)
                        except Exception as e:
                            print(f"删除文件夹失败 {pdir}: {e}")
                            QMessageBox.warning(self.view, "删除失败", f"无法删除文件夹: {pdir}\n错误: {e}")
            
            self.processed_parent_dirs.clear()
    ```

---

## 验证计划

1.  **单元测试验证**：确保现有的 pytest 运行无恙。
2.  **手动测试验证**：
    *   **磁力屏蔽验证**：拖入本地视频进行刮削，右侧磁力表格无内容；手动输入番号任务，右侧正常显示磁力。
    *   **原文件位置显示验证**：选中导入的任务，在详情面板能够正确看到原文件的绝对路径。
    *   **空文件夹清理验证**：在一个临时空文件夹下放置一个视频，导入并整理。整理完成后，原视频成功移走，弹出询问对话框，选择“是”，验证该临时文件夹已被正确删除。
