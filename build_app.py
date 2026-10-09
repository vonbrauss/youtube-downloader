"""Build a standalone macOS app without bundling any system download tools."""
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    if platform.system() != "Darwin":
        raise SystemExit("Build this macOS app on a Mac.")
    root = Path(__file__).resolve().parent
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication
    qt = QApplication.instance() or QApplication([])
    iconset = root / "build" / "icon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    svg = QSvgRenderer(str(root / "assets" / "icon.svg"))
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            pixels = size * scale
            pixmap = QPixmap(pixels, pixels)
            pixmap.fill(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            svg.render(painter, QRectF(0, 0, pixels, pixels))
            painter.end()
            pixmap.save(str(iconset / f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"))
    from PIL import Image
    with Image.open(iconset / "icon_512x512@2x.png") as image:
        image.save(root / "assets" / "icon.icns", format="ICNS")
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(root / "build" / "pyinstaller-cache")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(root / "YouTubeDownloader.spec")], cwd=root, check=True)
    print(f"Built: {root / 'dist' / 'YouTube Downloader.app'}")


if __name__ == "__main__":
    main()
