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

# 调用 pyinstaller 进行打包 (使用已定制 Info.plist 的 spec 配置文件以注入 macOS 隐私权限描述)
# 用 python3 -m 方式调用，不依赖 pyinstaller 命令是否在 PATH 中
python3 -m PyInstaller --noconfirm "JAV_SCRAPER_mac.spec"

echo "macOS 打包成功，打包文件生成于 dist/ 目录。"
