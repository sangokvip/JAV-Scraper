# -*- mode: python ; coding: utf-8 -*-
"""
Windows 打包配置（PyInstaller 6.x）。
与 JAV_SCRAPER_mac.spec 保持同构：版本号唯一来源 config.APP_VERSION，
产物为 dist/JAV SCRAPER/ 目录（内含 JAV SCRAPER.exe），由 build_win.bat / CI 再压缩成 zip。
"""
import re
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct,
    VarFileInfo, VarStruct,
)

# 用正则读版本号，避免 import config 触发建目录副作用
APP_VERSION = re.search(
    r"APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]",
    open('config.py', encoding='utf-8').read()
).group(1)


def _version_tuple(ver: str):
    nums = [int(x) for x in re.findall(r'\d+', ver)][:4]
    return tuple(nums + [0] * (4 - len(nums)))


# exe 属性 → 详细信息 里显示的版本资源
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_version_tuple(APP_VERSION),
        prodvers=_version_tuple(APP_VERSION),
        mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0),
    ),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('CompanyName', 'sangokvip'),
            StringStruct('FileDescription', 'JAV SCRAPER'),
            StringStruct('FileVersion', APP_VERSION),
            StringStruct('InternalName', 'JAV SCRAPER'),
            StringStruct('LegalCopyright', 'MIT License'),
            StringStruct('OriginalFilename', 'JAV SCRAPER.exe'),
            StringStruct('ProductName', 'JAV SCRAPER'),
            StringStruct('ProductVersion', APP_VERSION),
        ])]),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)

datas = [('third_party_config.json', '.'), ('cookies.json', '.'), ('lib', 'lib'), ('gui', 'gui'), ('player', 'player')]
binaries = []
# flask 由 player_service 动态加载（importlib），静态分析发现不了，必须显式声明
hiddenimports = ['flask']
# curl_cffi 依赖 libcurl DLL 与 cffi 后端，交给 collect_all 一并收集
tmp_ret = collect_all('curl_cffi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 用不到的 Qt 大模块直接排除，缩小体积（PySide6 hook 默认会带上被 import 的模块）
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore',
              'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtMultimedia', 'PySide6.QtCharts',
              'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JAV SCRAPER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX 压缩过的 Qt DLL 常被杀软误报，且会拖慢启动，关闭
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='JAV SCRAPER',
)
