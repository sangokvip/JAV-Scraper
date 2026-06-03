# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('third_party_config.json', '.'), ('cookies.json', '.'), ('lib', 'lib'), ('gui', 'gui')]
binaries = []
hiddenimports = []
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
    excludes=[],
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JAV SCRAPER',
)
app = BUNDLE(
    coll,
    name='JAV SCRAPER.app',
    icon='icon.icns',
    bundle_identifier='com.sangokvip.javscraper',
    info_plist={
        'CFBundleDisplayName': 'JAV SCRAPER',
        'CFBundleName': 'JAV SCRAPER',
        'NSRequiresAquaSystemAppearance': 'No',
        'NSDocumentsFolderUsageDescription': '需要访问文档文件夹以整理视频',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹以整理视频',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件夹以整理视频',
        'NSNetworkVolumesUsageDescription': '需要访问网络共享卷（NAS 等）以整理您的影片和写入元数据',
        'NSRemovableVolumesUsageDescription': '需要访问移动硬盘/U盘以整理您的影片和写入元数据',
    }
)
