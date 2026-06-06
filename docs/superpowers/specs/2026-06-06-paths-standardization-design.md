# JAV SCRAPER 路径规范化与内置资源打包设计文档

本文档定义了 JAV SCRAPER 数据存储路径规范化、内置标签库重构以及用户配置迁移的设计细节。

## 1. 背景与目标
目前，软件在运行时会将一些内部配置/状态备份（如 `cookies.json`、`settings_backup.json`、`tasks_backup.json`）和默认的 `output/` 输出目录生成在应用程序同级目录下。
这种做法在打包发布后存在以下问题：
1. **用户体验差**：在安装目录（如 `/Applications` 或 `/Users/mac/Desktop`）直接生成杂乱的配置文件及文件夹，影响美观。
2. **写权限风险**：在 macOS 的 `/Applications` 或 Windows 的 `C:\Program Files` 目录下，普通用户运行程序没有写入权限，会导致保存配置或导出时发生权限崩溃。

**优化目标**：
* 配置文件移动到操作系统的标准应用数据目录中。
* 默认输出目录移动到用户的“下载”目录下的专用文件夹。
* 将静态加密标签数据库打包进程序，避免外置。
* 提供平滑的配置自动迁移机制，用户升级无感。

---

## 2. 详细设计

### 2.1 路径层级重新规划
在 `config.py` 中重构路径体系：

1. **`BUNDLE_DIR`**（只读资源目录）：保持不变。依然指向 PyInstaller 释放只读文件的 `sys._MEIPASS`（打包态）或源码根目录（开发态）。
2. **`DATA_DIR`**（标准用户数据目录）：
   * **Windows**: `%APPDATA%/JAV SCRAPER` (例如 `C:\Users\username\AppData\Roaming\JAV SCRAPER`)
   * **macOS**: `~/Library/Application Support/JAV SCRAPER`
   * **Linux/其他**: `~/.config/JAV SCRAPER`
3. **`PROJECT_ROOT`**：保持指向 `DATA_DIR` 的兼容性别名，以便 `task_persister.py` 自动在新路径下读取/保存 `settings_backup.json` 和 `tasks_backup.json`。
4. **`OUTPUT_DIR['root']`**（默认输出保存目录）：
   * 重设默认值为：`~/Downloads/JAV SCRAPER` （用户可随时在 UI 中修改覆盖）。
   * 确保只在用户开始刮削、整理或保存需要对应文件夹时，才按需动态创建 `csv`、`json`、`images`、`magnets` 等子目录，而不是在软件启动时就强行在用户的下载目录下创建空目录。

### 2.2 自动迁移机制 (Auto-Migration)
为避免用户升级后丢失已登录的 Cookie 或设置：
在 `config.py` 初始化时执行数据迁移逻辑：
* 如果 `DATA_DIR` 下不存在 `cookies.json`，但老目录（原开发态根目录或原打包态的可写外置目录）下存在 `cookies.json`，则将其复制到新 `DATA_DIR` 下。
* 同理，对 `settings_backup.json` 和 `tasks_backup.json` 进行检测与拷贝迁移。
* 迁移完成后，删除老目录下的这三个文件以保持整洁。

### 2.3 内置标签库 relocation
* **文件移动**：将 `output/tags_database.enc` 移动到 `lib/tags_database.enc`。
* **读取定位**：
  * 修改 `lib/tag_manager.py` 和 `ultimate_provider.py`，不再从可写的 `output` 文件夹中加载 `tags_database.enc`，而是统一从 `BUNDLE_DIR/lib/tags_database.enc`（即 `Path(__file__).parent / 'tags_database.enc'`) 读取该只读库。
* **打包脚本**：不需要修改 PyInstaller spec 文件，因为 spec 中已配置 `('lib', 'lib')`，移动后标签库会自动包含进二进制文件中。

---

## 3. 影响分析与测试用例

### 3.1 影响分析
* 依赖 `config.COOKIE_FILE` 的模块：`gui/controller.py`、`lib/login.py` 均不受直接修改影响，因为它们通过全局导入获取路径，屏蔽了底层路径转移。
* 依赖 `gui/task_persister.py` 的备份模块：读取路径通过 `config.PROJECT_ROOT` 动态定位，不受影响。
* 依赖 `config.OUTPUT_DIR` 初始化的模块：初始化从启动时强制创建改为按需创建，保证了下载目录的干净。

### 3.2 测试验证
* **全新安装测试**：删除所有旧配置，启动软件，确认标准用户数据目录（如 `~/Library/Application Support/JAV SCRAPER`）成功创建并包含默认的配置文件；同时确认用户的下载目录下未被提前创建空文件夹。
* **升级迁移测试**：人为在应用同级目录下放置含有伪数据的 `cookies.json` / `settings_backup.json`，启动软件，验证是否自动迁移至标准应用数据目录中且原有配置正常加载，并且原应用同级目录下的对应文件被清理。
* **内置标签库读取测试**：在开发态和打包态下分别运行，执行一次标签过滤或检索，确认内置标签可以正确被解密加载。
