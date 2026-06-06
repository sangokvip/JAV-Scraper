# JAV SCRAPER 路径规范化与内置资源打包 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将软件运行时生成的三个 JSON 配置文件移动到操作系统的标准应用数据目录下，将默认导出目录重设至用户 Downloads/ 目录下，并将只读加密标签库内置打包，以避免污染应用程序所在目录并规避权限问题。

**Architecture:** 
1. 在 `config.py` 中重构可写用户数据目录 `DATA_DIR` 的定位逻辑（使用标准平台路径）。
2. 在 `config.py` 初始化时加入老配置自动复制迁移与旧文件清理机制。
3. 调整内置加密标签库 `tags_database.enc` 到 `lib/` 目录下，并更新 `lib/tag_manager.py` 中对其的读取路径，通过 PyInstaller 原生打包。
4. 将默认输出目录设为用户的下载目录，并将子文件夹的创建延迟到任务实际执行时。

**Tech Stack:** Python 3, PySide6, PyInstaller (Spec/Build)

---

## 计划分解与实施步骤

### Task 1: 移动内置标签数据库并调整读取路径

**Files:**
- Create/Move: `lib/tags_database.enc`
- Modify: `lib/tag_manager.py:25-28`

- [ ] **Step 1: 将标签数据库文件从 `output/` 移动至 `lib/` 目录**
  * 将项目中的 `output/tags_database.enc` 移动/复制到 `lib/tags_database.enc`。
  * 可在终端运行：
    ```bash
    cp output/tags_database.enc lib/tags_database.enc
    ```

- [ ] **Step 2: 修改 `lib/tag_manager.py` 中的数据库路径定位**
  * 修改 `lib/tag_manager.py` 构造函数第 25-28 行中的 `database_path` 默认值。
  * 目标代码替换为：
    ```python
    if database_path is None:
        database_path = Path(__file__).parent / "tags_database.enc"
    else:
        database_path = Path(database_path)
    ```

- [ ] **Step 3: 运行验证**
  * 运行现有测试或诊断脚本，确认 `TagManager` 在加载时不报错。
  * 可以在 Python 终端运行：
    ```python
    from lib.tag_manager import get_tag_manager
    manager = get_tag_manager()
    print("Tags loaded:", len(manager.get_all_tags()))
    ```
  * 预期输出：`Tags loaded: 3000+` (或者具体的标签数量)，无报错。

---

### Task 2: 重构 `config.py` 路径定位与添加自动迁移逻辑

**Files:**
- Modify: `config.py`

- [ ] **Step 1: 修改 `DATA_DIR` 与 `PROJECT_ROOT` 的计算逻辑**
  * 修改 `config.py` 中 `DATA_DIR` 的计算，支持操作系统标准的应用数据目录。
  * 目标代码段：
    ```python
    # 计算平台标准的 User App Data 目录
    def get_user_data_dir() -> Path:
        if sys.platform == 'win32':
            app_data = os.environ.get('APPDATA')
            if app_data:
                base_dir = Path(app_data)
            else:
                base_dir = Path.home() / 'AppData' / 'Roaming'
        elif sys.platform == 'darwin':
            base_dir = Path.home() / 'Library' / 'Application Support'
        else:
            base_dir = Path.home() / '.config'
        return base_dir / 'JAV SCRAPER'

    USER_DATA_DIR = get_user_data_dir()
    try:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    if getattr(sys, 'frozen', False):
        BUNDLE_DIR = Path(sys._MEIPASS)
        DATA_DIR = USER_DATA_DIR
    else:
        BUNDLE_DIR = Path(__file__).parent
        DATA_DIR = USER_DATA_DIR
    
    PROJECT_ROOT = DATA_DIR
    ```

- [ ] **Step 2: 修改默认输出路径并延迟文件夹创建**
  * 修改 `OUTPUT_DIR` 指向用户下载目录中的 `JAV SCRAPER` 文件夹。
  * 移出在 `config.py` 启动阶段立即强制创建 `OUTPUT_DIR` 子目录的循环。
  * 目标代码替换为：
    ```python
    # 默认输出路径设为用户的下载目录下的 JAV SCRAPER 文件夹
    OUTPUT_DIR = {
        'root': Path.home() / 'Downloads' / 'JAV SCRAPER',
        'csv': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'csv',
        'json': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'json',
        'images': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'images',
        'magnets': Path.home() / 'Downloads' / 'JAV SCRAPER' / 'magnets',
    }

    # 提供一个函数按需创建输出目录，防止启动时强行创建
    def ensure_output_dirs():
        for dir_path in OUTPUT_DIR.values():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
    ```

- [ ] **Step 3: 添加老配置到新标准数据目录的自动迁移与清理逻辑**
  * 在 `config.py` 文件底部，`COOKIE_FILE` 初始化及原有复制逻辑后面，添加配置迁移逻辑：
    ```python
    # 自动迁移历史配置文件逻辑
    def migrate_legacy_configs():
        # 原有的老配置文件位置 (在运行目录下)
        if getattr(sys, 'frozen', False):
            exe_path = Path(sys.executable)
            exe_dir = exe_path.parent
            if "Contents/MacOS" in str(exe_dir):
                legacy_dir = exe_dir.parent.parent.parent
            else:
                legacy_dir = exe_dir
        else:
            legacy_dir = Path(__file__).parent

        files_to_migrate = ['cookies.json', 'settings_backup.json', 'tasks_backup.json']
        
        for filename in files_to_migrate:
            legacy_file = legacy_dir / filename
            new_file = DATA_DIR / filename
            
            # 如果老目录文件存在，且新目录文件不存在
            if legacy_file.exists() and not new_file.exists():
                try:
                    import shutil
                    shutil.copyfile(str(legacy_file), str(new_file))
                    print(f"成功迁移历史配置: {filename} -> {new_file}")
                except Exception as e:
                    print(f"迁移配置 {filename} 失败: {e}")
            
            # 迁移完成后，如果老目录仍有文件，尝试将其安全清理以防污染
            if legacy_file.exists() and new_file.exists():
                try:
                    # 避免在开发态直接把开发配置文件删了
                    if getattr(sys, 'frozen', False) or str(legacy_file) != str(new_file):
                        # 如果是 cookies.json 且属于开发根目录，可选择保留，但打包环境下建议清理
                        os.remove(str(legacy_file))
                        print(f"已清理历史残留文件: {legacy_file}")
                except Exception as e:
                    pass

    migrate_legacy_configs()
    ```

---

### Task 3: 适配输出目录延迟创建逻辑

**Files:**
- Modify: `gui/controller.py`

- [ ] **Step 1: 在启动或导入任务等需要真正写入输出目录的逻辑处调用 `ensure_output_dirs`**
  * 在 `gui/controller.py` 的 `start_scraping` (启动刮削) 与 `start_organizing` (启动整理) 中，确保输出路径创建完成。
  * 引入 `from config import ensure_output_dirs`。
  * 在 `start_scraping` 和 `start_organizing` 顶部，调用 `ensure_output_dirs()`。

- [ ] **Step 2: 运行测试并验证迁移与自动创建功能**
  * 执行 `python3 main.py` 运行软件，查看原先在项目根目录下自动创建的 `cookies.json`、`settings_backup.json` 等文件，在新启动时是否被迁移到了 macOS 的 `~/Library/Application Support/JAV SCRAPER/`，且原同级目录被清理。
  * 确认在用户的 `~/Downloads/JAV SCRAPER` 没有任务执行前不被强行创建，一旦开启刮削后该目录被正常自动创建。

---

### Task 4: 追加工作日志与本地构建包验证

**Files:**
- Modify: `docs/migrations/CASCADE_WORKLOG.md`
- Build verification

- [ ] **Step 1: 追加记录到 `CASCADE_WORKLOG.md`**
  * 读取最后一条记录，并追加关于“路径规范化与内置标签库重组”的变更细节。

- [ ] **Step 2: macOS 本地打包构建与测试**
  * 运行打包脚本：
    ```bash
    sh build_mac.sh
    ```
  * 运行 `dist/JAV SCRAPER/JAV SCRAPER`（或通过 build_dmg.sh 打包后打开），测试刮削功能是否完美正常。
