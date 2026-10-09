from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from .model import Storage
from .theme import STYLE
from .window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Downloader")
    app.setOrganizationName("Local Desktop")
    app.setApplicationVersion("0.1.0")
    app.setFont(QFont(".AppleSystemUIFont", 13))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    assets = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets"
    if (assets / "icon.svg").exists():
        app.setWindowIcon(QIcon(str(assets / "icon.svg")))
    if "--smoke-test" in sys.argv:
        # Packaging verification never changes system tools or real user data.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(prefix="youtube-downloader-smoke-") as directory:
            window = MainWindow(Storage(Path(directory)), check_system=False)
            window.show()
            QTimer.singleShot(500, window.close)
            code = app.exec()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
            sys.exit(code)
    # Prevent two instances writing the same queue and updating Homebrew together.
    name = "local.youtube-downloader." + str(__import__("os").getuid())
    socket = QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(400):
        socket.write(b"activate")
        socket.waitForBytesWritten(400)
        return
    QLocalServer.removeServer(name)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name):
        QMessageBox.warning(None, "Could not start", server.errorString())
        return
    window = MainWindow()
    def activate():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnectFromServer()
            connection.deleteLater()
        window.showNormal()
        window.raise_()
        window.activateWindow()
    server.newConnection.connect(activate)
    window.show()
    code = app.exec()
    server.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    sys.exit(code)
