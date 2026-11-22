# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 配置：跨平台单文件打包，并裁剪未使用的 Qt/Pillow 组件。"""
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

# Windows 专属 DLL / pyd；非 Windows 上不匹配任何条目。
WINDOWS_DROP_EXACT = {
    "pyside6\\opengl32sw.dll",
    "pyside6\\libegl.dll",
    "pyside6\\libglesv2.dll",
    "pyside6\\d3dcompiler_47.dll",
    "pyside6\\qt6quick.dll",
    "pyside6\\qt6qml.dll",
    "pyside6\\qt6qmlmodels.dll",
    "pyside6\\qt6pdf.dll",
    "pyside6\\qt6virtualkeyboard.dll",
    "pyside6\\qt6svg.dll",
    "pyside6\\qt6opengl.dll",
    "pyside6\\qt6openglwidgets.dll",
    "pyside6\\plugins\\platforms\\qdirect2d.dll",
    "pyside6\\plugins\\styles\\qmodernwindowsstyle.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "_ssl.pyd",
}

DROP_EXACT = WINDOWS_DROP_EXACT if IS_WINDOWS else set()
DROP_DIR_NAMES = {"translations", "imageformats", "tls"}
PIL_EXTENSION = ".pyd" if IS_WINDOWS else ".so"


def _normalized_name(item):
    return str(item[0]).replace("/", "\\").lower()


def _keep_item(item):
    name = _normalized_name(item)
    if name in DROP_EXACT:
        return False
    parts = [part for part in name.split("\\") if part]
    if any(part in DROP_DIR_NAMES for part in parts):
        return False
    # 二维码只需要 PIL 核心图像模块，不需要 AVIF/WebP/字体等编解码器。
    if name.startswith("pil\\") and name.endswith(PIL_EXTENSION) and "_imaging." not in name:
        return False
    return True


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['qrcode', 'PySide6.QtNetwork'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'numpy',
        'matplotlib',
        'pytest',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtPdf',
        'PySide6.QtSvg',
        'PySide6.QtOpenGL',
        'PySide6.QtMultimedia',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PIL.AvifImagePlugin',
        'PIL.WebPImagePlugin',
    ],
    noarchive=False,
    optimize=0,
)

a.binaries = [item for item in a.binaries if _keep_item(item)]
a.datas = [item for item in a.datas if _keep_item(item)]

pyz = PYZ(a.pure)

exe_options = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=IS_MACOS,
    target_arch=None,
)

if IS_MACOS:
    # macOS 第一阶段交付未签名单文件可执行程序；.app/签名/公证留待第二阶段。
    exe_options.update(codesign_identity=None, entitlements_file=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LanFileShare',
    **exe_options,
)
