@echo off
chcp 65001 > nul
:: 自动化打包脚本 (Windows) — 修复版
:: 注意: 本脚本针对 Python 3.10.x 进行了版本约束修复
echo [1/4] 安装全部依赖...
python -m pip install -r requirements.txt --quiet
python -m pip install "pyinstaller==5.13.2" "pycparser==2.22" --quiet

echo [2/4] 生成图标文件...
python convert_icon.py

echo [3/4] 创建必要配置文件...
if not exist cookies.json (
  echo {} > cookies.json
)

if not exist third_party_config.json (
  echo {"default_adapter": "javdb", "adapters": {"javdb": {"enabled": true, "domain_index": 0}}} > third_party_config.json
)

echo [4/4] 开始 PyInstaller 打包...
pyinstaller --noconfirm "JAV_SCRAPER_win.spec"

if %ERRORLEVEL% EQU 0 (
  echo.
  echo ================================================
  echo  打包成功！exe 文件位于 dist\JAV SCRAPER\ 目录
  echo ================================================
) else (
  echo.
  echo [ERROR] 打包失败，请检查上方错误信息。
)
pause
