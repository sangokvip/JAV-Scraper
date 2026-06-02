# JAV SCRAPER 跨平台打包与图标集成设计规范

本文档定义了 JAV SCRAPER 项目的图标生成、窗口图标绑定以及针对 macOS 和 Windows 平台的 PyInstaller 打包流程。

## 1. 目标 (Objectives)
- **多尺寸图标转换**：将之前生成的艺术 Logo (`app_icon_1780383540032.png`) 自动转换为适用于各操作系统的格式，包括 `.ico` (Windows) 和 `.icns` (macOS)。
- **应用窗口集成**：实现客户端运行和打包时能够自适应加载并展示窗口图标。
- **跨平台打包支持**：为 macOS 平台提供一键生成 `.app` 的打包脚本，并为 Windows 提供一键生成 `.exe` 的批处理脚本。同时处理好三方依赖库（如 `curl_cffi` 的动态链接库）在打包时的收集问题。

---

## 2. 图标生成与转换设计 (Icon Conversion Design)
利用临时 Python 转换脚本 `convert_icon.py` 进行图标生成：
- **Pillow 依赖**：如果当前环境没有安装 `Pillow`，我们需要临时通过 pip 安装它。
- **文件输出**：
  - `gui/icon.png` (256x256，用于 PyQt/PySide QIcon)
  - `icon.ico` (包含 16, 32, 48, 64, 128, 256 等多尺寸的 Windows 图标文件)
  - `icon.icns` (macOS 专用图标格式)

---

## 3. UI 窗口集成设计 (UI Window Integration)
在 `gui/main_window.py` 构造函数中引入窗口图标：
```python
from PySide6.QtGui import QIcon
# 引入 icon.png
icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
if os.path.exists(icon_path):
    self.setWindowIcon(QIcon(icon_path))
```
并在打包参数中确保 `gui/icon.png` 被正确复制到打包文件夹中，以便运行中的程序可以动态加载它。

---

## 4. 打包机制与脚本设计 (Packaging Scripts)

由于打包工具 PyInstaller 不支持跨平台交叉编译，需针对两平台使用独立的打包脚本：

### macOS 平台 (`build_mac.sh`)
```bash
#!/bin/bash
# 自动生成图标并使用 PyInstaller 打包 (macOS)
pip install Pillow pyinstaller
python3 convert_icon.py

pyinstaller --noconfirm --onedir --windowed \
  --name="JAV SCRAPER" \
  --icon="icon.icns" \
  --add-data="gui/icon.png:gui" \
  --add-data="third_party_config.json:." \
  --add-data="cookies.json:." \
  --add-data="lib:lib" \
  --add-data="gui:gui" \
  --collect-all curl_cffi \
  main.py
```

### Windows 平台 (`build_win.bat`)
```bat
@echo off
:: 自动生成图标并使用 PyInstaller 打包 (Windows)
pip install Pillow pyinstaller
python convert_icon.py

pyinstaller --noconfirm --onedir --windowed ^
  --name="JAV SCRAPER" ^
  --icon="icon.ico" ^
  --add-data="gui/icon.png;gui" ^
  --add-data="third_party_config.json;." ^
  --add-data="cookies.json;." ^
  --add-data="lib;lib" ^
  --add-data="gui;gui" ^
  --collect-all curl_cffi ^
  main.py
pause
```

---

## 5. 验证计划 (Verification Plan)
- **图标验证**：转换后，校验 `gui/icon.png`、`icon.ico` 和 `icon.icns` 是否存在。
- **本地运行验证**：运行 `python3 main.py`，查看窗口标题栏的图标是否正确渲染。
- **macOS 打包验证**：运行 `sh build_mac.sh`，验证生成在 `dist/` 下的 `JAV SCRAPER.app` 能够成功打开，且包含正确的 Dock 与窗口图标，刮削整理测试完全正常。
