"""程序入口。"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from app.ui import MainWindow

SINGLE_INSTANCE_KEY = "LanFileShare.SingleInstance"


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LanFileShare")
    app.setOrganizationName("LanFileShare")
    app.setStyle("Fusion")

    # 单实例检查：重复启动时直接退出，避免端口占用与配置写冲突。
    probe = QLocalSocket()
    probe.connectToServer(SINGLE_INSTANCE_KEY)
    if probe.waitForConnected(200):
        probe.close()
        return 0
    probe.close()
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
    instance_server = QLocalServer()
    instance_server.listen(SINGLE_INSTANCE_KEY)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
