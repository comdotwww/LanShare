# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 配置：裁剪未使用的 Qt/Pillow 组件，减小单文件体积。"""

DROP_EXACT = {
    # Qt 的可选模块：本程序只使用 Widgets / Gui / Core / Network。
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
    # 不使用 Qt SSL / 网络加密：仅用 QLocalSocket 做单实例检测。
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "_ssl.pyd",
}

DROP_PREFIXES = (
    "pyside6\\translations\\",
    "pyside6\\plugins\\imageformats\\",
    "pyside6\\plugins\\tls\\",
)


def _normalized_name(item):
    return str(item[0]).replace("/", "\\").lower()


def _keep_item(item):
    name = _normalized_name(item)
    if name in DROP_EXACT:
        return False
    if any(name.startswith(prefix) for prefix in DROP_PREFIXES):
        return False
    # 二维码只需要 PIL 的核心图像模块，不需要 AVIF/WebP/字体等编解码器。
    if name.startswith("pil\\") and name.endswith(".pyd") and "_imaging." not in name:
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LanFileShare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
