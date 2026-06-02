#!/bin/bash
# 自动化打包 DMG 脚本 (macOS)
set -e

APP_NAME="JAV SCRAPER"
DMG_NAME="JAV_SCRAPER_macOS.dmg"
DIST_DIR="dist"
TEMP_DIR="dmg_temp"

echo "开始构建 DMG 安装包..."

# 检查 .app 是否存在
if [ ! -d "${DIST_DIR}/${APP_NAME}.app" ]; then
  echo "错误: 未找到 ${DIST_DIR}/${APP_NAME}.app，请先运行 build_mac.sh 打包应用程序。"
  exit 1
fi

# 清理历史临时目录和 DMG
rm -rf "${TEMP_DIR}"
rm -f "${DIST_DIR}/${DMG_NAME}"

# 创建临时打包目录
mkdir -p "${TEMP_DIR}"

echo "1. 正在复制应用程序至临时目录..."
cp -R "${DIST_DIR}/${APP_NAME}.app" "${TEMP_DIR}/"

echo "2. 正在创建 Applications 快捷方式..."
ln -s /Applications "${TEMP_DIR}/Applications"

echo "3. 正在生成 DMG 磁盘映像文件..."
hdiutil create -volname "${APP_NAME} Installer" -srcfolder "${TEMP_DIR}" -ov -format UDZO "${DIST_DIR}/${DMG_NAME}"

echo "4. 正在清理临时文件..."
rm -rf "${TEMP_DIR}"

echo "=============================================="
echo "DMG 构建成功！输出路径: ${DIST_DIR}/${DMG_NAME}"
echo "您可以直接将该 DMG 文件上传到 GitHub Release 中。"
echo "=============================================="
