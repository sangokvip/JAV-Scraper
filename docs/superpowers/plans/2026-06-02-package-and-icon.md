# JAV SCRAPER 打包与图标集成实施计划

本项目将把当前的 Python PyQt/PySide6 桌面程序打包为 macOS (.app) 和 Windows (.exe) 的专属格式，并且在打包前生成各平台专属的高级艺术图标并设置给主窗口。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Python JAV SCRAPER 界面软件打包为 macOS .app 和 Windows .exe，并在打包前集成生成的专属艺术 Logo 图标。

**Architecture:** 通过 convert_icon.py（基于 Pillow）将 PNG 图标转换为多分辨率的 .ico 与 .icns 格式，并在 MainWindow 中动态加载 QIcon。然后编写 build_mac.sh / build_win.bat 通过 PyInstaller --windowed 并包含 curl_cffi 所有底层 C 的二进制动态链接库打包程序。

**Tech Stack:** Python 3, PySide6, Pillow, PyInstaller, curl_cffi

---

### Task 1: 图标拷贝与格式转换

**Files:**
- Create: `convert_icon.py`

- [ ] **Step 1: 拷贝原始图标文件到项目根目录**
  * 拷贝路径：`/Users/mac/.gemini/antigravity-ide/brain/4a21bc74-ed22-4a14-9cee-d7204a6bae2a/app_icon_1780383540032.png` -> `/Users/mac/Documents/GitHub/ javdb-api-scraper/app_icon_orig.png`。
- [ ] **Step 2: 安装依赖库 Pillow**
  * 执行命令：`python3 -m pip install Pillow`。
- [ ] **Step 3: 编写 convert_icon.py 脚本**
  * 实现转换逻辑，核心代码：
  ```python
  import os
  from PIL import Image

  def main():
      orig_path = "app_icon_orig.png"
      if not os.path.exists(orig_path):
          print(f"Error: {orig_path} not found.")
          return
      
      img = Image.open(orig_path)
      
      # 1. 存为 gui/icon.png
      os.makedirs("gui", exist_ok=True)
      img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
      img_resized.save("gui/icon.png", format="PNG")
      print("Generated gui/icon.png")
      
      # 2. 存为 icon.ico (多尺寸)
      img.save("icon.ico", format="ICO", sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
      print("Generated icon.ico")
      
      # 3. 存为 icon.icns
      img.save("icon.icns", format="ICNS")
      print("Generated icon.icns")

  if __name__ == "__main__":
      main()
  ```
- [ ] **Step 4: 运行 convert_icon.py 生成图标**
  * 执行：`python3 convert_icon.py`
  * 校验文件生成情况。

---

### Task 2: 绑定 UI 窗口图标并测试

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: 修改 gui/main_window.py 以引入窗口图标**
  * 搜索 `self.setWindowTitle` 并在下面添加窗口图标设置。
- [ ] **Step 2: 运行测试**
  * 运行：`pytest` 确保现有测试通过。

---

### Task 3: 编写打包脚本并执行 macOS 打包

**Files:**
- Create: `build_mac.sh`
- Create: `build_win.bat`

- [ ] **Step 1: 编写 build_mac.sh 和 build_win.bat**
  * 详细配置 PyInstaller 命令。
- [ ] **Step 2: 安装 PyInstaller 打包依赖**
  * 执行：`python3 -m pip install pyinstaller`
- [ ] **Step 3: 执行 macOS 本地打包**
  * 运行：`sh build_mac.sh`
  * 验证最终是否在 `dist/` 目录下生成 `JAV SCRAPER.app`。

---

### Task 4: 补充 README 说明与工作志记录

**Files:**
- Modify: `README.md`
- Modify: `docs/migrations/CASCADE_WORKLOG.md`

- [ ] **Step 1: 补充 README.md 打包指南**
  * 说明 Windows 与 macOS 下如何一键打包。
- [ ] **Step 2: 追加 CASCADE_WORKLOG.md 条目**
  * 记录所有完成的技术细节，并进行 Git 提交。
