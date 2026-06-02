@echo off
:: 自动化打包脚本 (Windows)
python -m pip install Pillow pyinstaller
python convert_icon.py

if not exist cookies.json (
  echo {} > cookies.json
)

if not exist third_party_config.json (
  echo {"default_adapter": "javdb", "adapters": {"javdb": {"enabled": true, "domain_index": 0}}} > third_party_config.json
)

pyinstaller --noconfirm --onedir --windowed ^
  --name="JAV SCRAPER" ^
  --icon="icon.ico" ^
  --add-data="third_party_config.json;." ^
  --add-data="cookies.json;." ^
  --add-data="lib;lib" ^
  --add-data="gui;gui" ^
  --collect-all curl_cffi ^
  main.py

echo Windows 打包成功，打包文件生成于 dist/ 目录。
pause
