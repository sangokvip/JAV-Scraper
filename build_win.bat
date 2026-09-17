@echo off
chcp 65001 > nul
setlocal
:: ============================================================
::  JAV SCRAPER — Windows 一键打包脚本
::  产物: dist\JAV SCRAPER\JAV SCRAPER.exe 以及 dist\JAV_SCRAPER_v<版本>_windows_x64.zip
::  要求: 已安装 Python 3.10 ~ 3.12（64 位），并加入 PATH
:: ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] 未找到 python，请先安装 Python 3.10+ 并勾选 "Add python.exe to PATH"。
  pause & exit /b 1
)

echo [1/5] 安装运行依赖与 PyInstaller...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install "pyinstaller>=6.0" --quiet
if %ERRORLEVEL% NEQ 0 ( echo [ERROR] 依赖安装失败 & pause & exit /b 1 )

echo [2/5] 生成图标文件...
python convert_icon.py
if %ERRORLEVEL% NEQ 0 ( echo [ERROR] 图标生成失败 & pause & exit /b 1 )

echo [3/5] 准备打包所需的配置文件...
if not exist cookies.json echo {} > cookies.json
if not exist third_party_config.json echo {"default_adapter": "javdb", "adapters": {"javdb": {"enabled": true, "domain_index": 0}}} > third_party_config.json

echo [4/5] PyInstaller 打包...
python -m PyInstaller --noconfirm --clean "JAV_SCRAPER_win.spec"
if %ERRORLEVEL% NEQ 0 ( echo [ERROR] 打包失败，请检查上方错误信息。 & pause & exit /b 1 )

echo [5/5] 压缩为可分发的 zip...
for /f "usebackq delims=" %%v in (`python -c "import re;print(re.search(r'APP_VERSION\s*=\s*.([0-9.]+)',open('config.py',encoding='utf-8').read()).group(1))"`) do set APP_VERSION=%%v
set ZIP_NAME=JAV_SCRAPER_v%APP_VERSION%_windows_x64.zip
if exist "dist\%ZIP_NAME%" del "dist\%ZIP_NAME%"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\JAV SCRAPER' -DestinationPath 'dist\%ZIP_NAME%' -CompressionLevel Optimal"

echo.
echo ================================================
echo  打包成功！
echo    可执行文件: dist\JAV SCRAPER\JAV SCRAPER.exe
echo    分发压缩包: dist\%ZIP_NAME%
echo ================================================
pause
