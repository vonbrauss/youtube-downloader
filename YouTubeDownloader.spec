# Build on macOS using build_app.py. yt-dlp stays external to this bundle.
from pathlib import Path
import re
import subprocess
import sys

python_library = Path(sys.base_prefix) / "Python"
load_commands = subprocess.check_output(["/usr/bin/otool", "-l", str(python_library)], text=True)
match = re.search(r"minos\s+(\d+(?:\.\d+)*)", load_commands)
minimum_macos = max(["14.0", match.group(1) if match else "14.0"], key=lambda v: tuple(map(int, v.split("."))))

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'assets' / 'icon.svg'), 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['yt_dlp', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtPdf', 'PySide6.QtMultimedia',
              'tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='YouTube Downloader', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='YouTube Downloader')
app = BUNDLE(
    coll,
    name='YouTube Downloader.app',
    icon=str(root / 'assets' / 'icon.icns'),
    bundle_identifier='local.youtube-downloader.desktop',
    info_plist={
        'CFBundleShortVersionString': '0.1.1',
        'CFBundleVersion': '2',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': minimum_macos,
        'NSHumanReadableCopyright': 'YouTube Downloader — local desktop application',
    },
)
