#!/bin/bash
# 自动化打包脚本 (macOS)
# 确保安装必要依赖
python3 -m pip install Pillow pyinstaller

# 生成最新图标
python3 convert_icon.py

# 确保配置文件存在，防止打包时文件缺失报错
if [ ! -f cookies.json ]; then
  echo "{}" > cookies.json
fi

if [ ! -f third_party_config.json ]; then
  echo '{"default_adapter": "javdb", "adapters": {"javdb": {"enabled": true, "domain_index": 0}}}' > third_party_config.json
fi

# 确保新安装的 pyinstaller 命令行工具在 PATH 中
export PATH="/Users/mac/Library/Python/3.9/bin:$PATH"

# 调用 pyinstaller 进行打包
pyinstaller --noconfirm --onedir --windowed \
  --name="JAV SCRAPER" \
  --icon="icon.icns" \
  --add-data="third_party_config.json:." \
  --add-data="cookies.json:." \
  --add-data="lib:lib" \
  --add-data="gui:gui" \
  --collect-all curl_cffi \
  main.py

echo "macOS 打包成功，打包文件生成于 dist/ 目录。"
