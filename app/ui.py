"""桌面端界面、设置与服务控制。"""
from __future__ import annotations

import queue
import re
import sys
import threading
import time
from pathlib import Path
from typing import Iterable, List
from urllib.parse import quote

import qrcode
from PySide6.QtCore import Qt, QEvent, QObject, QSize, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QGuiApplication,
    QImage,
    QIntValidator,
    QPalette,
    QPixmap,
    QShowEvent,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import load_config, normalize_base_path, save_config
from .i18n import LANGUAGES, Translator
from .network import lan_ip, list_bind_addresses
from .registry import Share, ShareRegistry, UploadFolder, UploadRegistry
from .server import LanHTTPServer, ShareRequestHandler

STYLE_TEMPLATE = """
* { font-family: "__FONT_FAMILY__", sans-serif; }
QWidget { color: #111827; font-size: __FS_BASE__px; }
QDialog, QMessageBox { background: #ffffff; color: #111827; }
QMainWindow, QWidget#central { background: #f5f7fb; }
QStatusBar { background: transparent; color: #6b7280; border: 0; }
QFrame#header { background: transparent; }
QLabel#appTitle { font-size: __FS_TITLE__px; font-weight: 700; color: #111827; }
QLabel#appSubtitle { font-size: __FS_BASE__px; color: #6b7280; }
QLabel#sectionTitle { font-size: __FS_SECTION__px; font-weight: 700; color: #111827; }
QLabel#sectionSubtitle { font-size: __FS_SMALL__px; color: #9ca3af; }
QLabel#hint { font-size: __FS_SMALL__px; color: #6b7280; }
QLabel#countBadge { padding: 3px 10px; border-radius: 9px; background: #eef2ff; color: #4338ca; font-size: __FS_SMALL__px; font-weight: 600; }
QLabel#statusBadge { padding: 6px 14px; border-radius: 12px; font-size: __FS_SMALL__px; font-weight: 600; }
QLabel#statusBadge[state="running"] { background: #dcfce7; color: #15803d; }
QLabel#statusBadge[state="stopped"] { background: #f3f4f6; color: #6b7280; }

QFrame#card { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; }
QTabWidget::pane { border: 0; background: transparent; top: -1px; }
QTabBar::tab { background: #f3f4f6; color: #6b7280; padding: 8px 18px; border-radius: 8px; margin-right: 6px; }
QTabBar::tab:selected { background: #ffffff; color: #2563eb; border: 1px solid #e5e7eb; font-weight: 600; }
QTabBar::tab:hover:!selected { background: #e5e7eb; }
QFrame#infoBox { background: #f8fafc; border: 1px solid #eef2f7; border-radius: 10px; }
QLabel#infoKey { color: #9ca3af; font-size: __FS_SMALL__px; }
QLabel#infoValue { color: #1f2937; font-size: __FS_SMALL__px; font-weight: 600; }
QLabel#infoValueLink { color: #2563eb; font-size: __FS_SMALL__px; font-weight: 600; }

QComboBox, QLineEdit, QFontComboBox {
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 20px;
    selection-background-color: #2563eb;
}
QComboBox:hover, QLineEdit:hover, QFontComboBox:hover { border-color: #93c5fd; }
QComboBox:focus, QLineEdit:focus, QFontComboBox:focus { border-color: #2563eb; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView { border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff; selection-background-color: #eff6ff; selection-color: #1d4ed8; }

QPushButton {
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 14px;
    color: #374151;
}
QPushButton:hover { background: #f9fafb; border-color: #93c5fd; }
QPushButton:pressed { background: #f3f4f6; }
QPushButton:disabled { color: #9ca3af; background: #f3f4f6; border-color: #e5e7eb; }
QPushButton#primaryButton { background: #2563eb; border-color: #2563eb; color: #ffffff; font-weight: 600; }
QPushButton#primaryButton:hover { background: #1d4ed8; border-color: #1d4ed8; }
QPushButton#primaryButton:disabled { background: #93c5fd; border-color: #93c5fd; color: #eff6ff; }
QPushButton#refreshButton { padding: 6px 12px; font-size: __FS_SMALL__px; border-radius: 8px; }
QPushButton#dangerButton { color: #b91c1c; border-color: #fecaca; }
QPushButton#dangerButton:hover { background: #fef2f2; border-color: #fca5a5; }

QFrame#dropZone { background: #f8fbff; border: 1.5px dashed #93c5fd; border-radius: 12px; }
QFrame#dropZone[active="true"] { background: #eff6ff; border-color: #2563eb; }
QLabel#dropTitle { font-size: __FS_DROP__px; font-weight: 600; color: #1d4ed8; }
QLabel#dropHint { font-size: __FS_SMALL__px; color: #6b7280; }
QLabel#emptyHint { color: #9ca3af; font-size: __FS_BASE__px; padding: 28px 10px; }
QCheckBox { spacing: 8px; }

QListWidget#shareList { background: transparent; border: 0; padding: 0; }
QListWidget#shareList::item { border: 0; background: transparent; }
QFrame#shareRow { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px; }
QFrame#shareRow[selected="true"] { border-color: #60a5fa; background: #f8fbff; }
QLabel#typeBadge { border-radius: 7px; padding: 4px 7px; font-size: __FS_TINY__px; font-weight: 600; }
QLabel#typeBadge[kind="file"] { background: #f3f4f6; color: #4b5563; }
QLabel#typeBadge[kind="directory"] { background: #dbeafe; color: #1d4ed8; }
QLabel#shareName { font-size: __FS_BASE__px; font-weight: 600; color: #111827; }
QLabel#sharePath, QLabel#shareLink { font-size: __FS_TINY__px; color: #9ca3af; }
QLabel#shareLink { color: #2563eb; }
QLabel#missingBadge { font-size: __FS_TINY__px; color: #b91c1c; }
QPushButton#rowButton { padding: 5px 9px; font-size: __FS_TINY__px; border-radius: 7px; }
QPushButton#rowPrimary { padding: 5px 9px; font-size: __FS_TINY__px; border-radius: 7px; background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
QPushButton#rowDanger { padding: 5px 9px; font-size: __FS_TINY__px; border-radius: 7px; color: #b91c1c; border-color: #fee2e2; }

QFrame#logCard { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; }
QPlainTextEdit#logView { background: #f8fafc; border: 1px solid #eef2f7; border-radius: 8px; color: #4b5563; font-family: Consolas, "__FONT_FAMILY__", monospace; font-size: __FS_TINY__px; padding: 6px; }
QLineEdit#qrLink { color: #2563eb; font-size: __FS_SMALL__px; }
"""


def build_stylesheet(font_family: str, font_size: int) -> str:
    """根据用户字体/字号生成 QSS，避免固定字号覆盖设置。"""
    family = str(font_family or "Microsoft YaHei UI").replace('"', "")
    base = max(9, min(22, int(font_size)))
    values = {
        "__FONT_FAMILY__": family,
        "__FS_BASE__": str(base),
        "__FS_TITLE__": str(base + 9),
        "__FS_SECTION__": str(base + 2),
        "__FS_SMALL__": str(max(9, base - 1)),
        "__FS_TINY__": str(max(9, base - 2)),
        "__FS_DROP__": str(base + 1),
    }
    stylesheet = STYLE_TEMPLATE
    for key, value in values.items():
        stylesheet = stylesheet.replace(key, value)
    return stylesheet


def make_light_palette() -> QPalette:
    """构造显式亮色调色板，避免系统暗色主题影响 Qt 控件。"""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#ffffff"))
    palette.setColor(QPalette.WindowText, QColor("#111827"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f9fafb"))
    palette.setColor(QPalette.Text, QColor("#111827"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#111827"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#374151"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9ca3af"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#9ca3af"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9ca3af"))
    return palette


def prepare_light_window(window: QWidget) -> None:
    window.setAttribute(Qt.WA_StyledBackground, True)
    window.setPalette(make_light_palette())


def force_light_title_bar(window: QWidget) -> None:
    """强制 Windows 窗口标题栏使用浅色，不受系统暗色模式影响。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(window.winId())
        if not hwnd:
            return
        # 19 适配 Windows 10 早期版本，20 为正式 DWM 属性。
        for attribute in (19, 20):
            value = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception:
        pass


class LightTitleBarFilter(QObject):
    """应用级过滤器：所有 Qt 对话框显示时强制浅色标题栏。"""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(obj, (QDialog, QMainWindow)):
            force_light_title_bar(obj)
        return False


class NumberEdit(QLineEdit):
    """可手动输入的整数输入框，保留 value/valueChanged 接口。"""

    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self.setValidator(QIntValidator(minimum, maximum, self))
        self.setText(str(max(minimum, min(maximum, int(value)))))
        self.textChanged.connect(self._emit_value)

    def _parsed_value(self) -> int | None:
        text = self.text().strip()
        if not text:
            return None
        try:
            value = int(text)
        except ValueError:
            return None
        return value if self._minimum <= value <= self._maximum else None

    def _emit_value(self, _text: str) -> None:
        value = self._parsed_value()
        if value is not None:
            self.valueChanged.emit(value)

    def value(self) -> int:
        value = self._parsed_value()
        return self._minimum if value is None else value

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.selectAll()

    def setValue(self, value: int) -> None:
        text = str(max(self._minimum, min(self._maximum, int(value))))
        if self.text() != text:
            self.setText(text)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = maximum
        self.setValidator(QIntValidator(minimum, maximum, self))
        if self.value() < minimum:
            self.setValue(minimum)


def _elide(text: str, limit: int) -> str:
    text = str(text)
    if len(text) <= limit:
        return text
    half = max(1, (limit - 1) // 2)
    return text[:half] + "…" + text[-half:]


class DropArea(QFrame):
    filesDropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(4)
        self.title_label = QLabel(objectName="dropTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.hint_label = QLabel(objectName="dropHint")
        self.hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.hint_label)

    def retranslate(self, i18n: Translator) -> None:
        self.title_label.setText(i18n.t("drop_title"))
        self.hint_label.setText(i18n.t("drop_hint"))

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.set_active(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.set_active(False)
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.filesDropped.emit(paths)
        else:
            event.ignore()


class ShareRow(QFrame):
    def __init__(self, share: Share, controller: "MainWindow") -> None:
        super().__init__()
        self.share = share
        self.controller = controller
        self.setObjectName("shareRow")
        self.set_selected(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        badge_text = controller.text("folder" if share.kind == "directory" else "file")
        badge = QLabel(badge_text, objectName="typeBadge")
        badge.setProperty("kind", share.kind)
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumWidth(58)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(Path(share.path).name or share.path, objectName="shareName")
        name.setToolTip(share.path)
        path = QLabel(_elide(share.path, 72), objectName="sharePath")
        path.setToolTip(share.path)
        link = QLabel(_elide(controller.share_url(share), 72), objectName="shareLink")
        link.setToolTip(controller.share_url(share))
        info.addWidget(name)
        info.addWidget(path)
        info.addWidget(link)
        if not Path(share.path).exists():
            info.addWidget(QLabel(controller.text("missing_path"), objectName="missingBadge"))
        root.addLayout(info, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        copy_btn = QPushButton(controller.text("copy_link"), objectName="rowPrimary")
        copy_btn.clicked.connect(lambda: controller.copy_link(share.token))
        qr_btn = QPushButton(controller.text("qr_code"), objectName="rowButton")
        qr_btn.clicked.connect(lambda: controller.show_qr(share.token))
        remove_btn = QPushButton(controller.text("remove"), objectName="rowDanger")
        remove_btn.clicked.connect(lambda: controller.remove_token(share.token))
        buttons.addWidget(copy_btn)
        buttons.addWidget(qr_btn)
        buttons.addWidget(remove_btn)
        root.addLayout(buttons)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseDoubleClickEvent(self, event) -> None:
        self.controller.open_share_path(self.share.token)
        super().mouseDoubleClickEvent(event)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setHeight(max(78, self.controller.font_size * 5 + 22))
        return hint


class LightMessageBox(QMessageBox):
    """亮色消息框，替代随系统主题变暗的原生 QMessageBox。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        prepare_light_window(self)
        self.setStyleSheet(
            "QMessageBox { background: #ffffff; color: #111827; }"
            "QLabel { color: #111827; }"
            "QPushButton { min-width: 84px; padding: 7px 14px; }"
        )

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        force_light_title_bar(self)


class FirewallNoticeDialog(QDialog):
    """首次启动前的防火墙操作引导。"""

    def __init__(self, i18n: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        prepare_light_window(self)
        self.i18n = i18n
        self.setWindowTitle(i18n.t("firewall_title"))
        self.setMinimumWidth(500)
        self.setMaximumWidth(640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        intro = QLabel(i18n.t("firewall_intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet("font-weight: 600;")
        layout.addWidget(intro)

        steps = QLabel(
            "\n\n".join(
                [
                    i18n.t("firewall_step1"),
                    i18n.t("firewall_step2"),
                    i18n.t("firewall_step3"),
                ]
            )
        )
        steps.setWordWrap(True)
        layout.addWidget(steps)

        warning = QLabel(i18n.t("firewall_warning"))
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b45309;")
        layout.addWidget(warning)

        self.ack_box = QCheckBox(i18n.t("firewall_ack"))
        layout.addWidget(self.ack_box)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton(i18n.t("firewall_cancel"))
        cancel_btn.clicked.connect(self.reject)
        self.continue_btn = QPushButton(i18n.t("firewall_continue"), objectName="primaryButton")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.accept)
        self.ack_box.toggled.connect(self.continue_btn.setEnabled)
        actions.addWidget(cancel_btn)
        actions.addWidget(self.continue_btn)
        layout.addLayout(actions)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        force_light_title_bar(self)


class SettingsDialog(QDialog):
    """字体、字号与语言设置；修改即时生效。"""

    def __init__(self, controller: "MainWindow", i18n: Translator) -> None:
        super().__init__(controller)
        prepare_light_window(self)
        self.controller = controller
        self.i18n = i18n
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.font_combo = QFontComboBox()
        self.font_combo.setEditable(False)
        self.font_combo.setCurrentFont(QFont(controller.font_family))
        self.size_spin = NumberEdit(9, 22, controller.font_size)
        self.lang_combo = QComboBox()

        self.font_label = QLabel()
        self.size_label = QLabel()
        self.lang_label = QLabel()
        form.addRow(self.font_label, self.font_combo)
        form.addRow(self.size_label, self.size_spin)
        form.addRow(self.lang_label, self.lang_combo)
        root.addLayout(form)

        self.preview_label = QLabel(objectName="sectionTitle")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(52)
        root.addWidget(self.preview_label)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #6b7280;")
        root.addWidget(self.hint_label)

        actions = QHBoxLayout()
        self.reset_btn = QPushButton(objectName="rowButton")
        self.reset_btn.clicked.connect(controller.reset_firewall_notice)
        close_btn = QPushButton(objectName="primaryButton")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(self.reset_btn)
        actions.addStretch(1)
        actions.addWidget(close_btn)
        root.addLayout(actions)

        current_language = i18n.language
        for label, code in LANGUAGES:
            self.lang_combo.addItem(label, code)
        index = self.lang_combo.findData(current_language)
        self.lang_combo.setCurrentIndex(index if index >= 0 else 0)

        self.font_combo.currentFontChanged.connect(self._apply)
        self.size_spin.valueChanged.connect(self._apply)
        self.lang_combo.currentIndexChanged.connect(self._apply)
        self._retranslate()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        force_light_title_bar(self)

    def _retranslate(self) -> None:
        i18n = self.i18n
        self.setWindowTitle(i18n.t("settings_title"))
        self.font_label.setText(i18n.t("font"))
        self.size_label.setText(f"{i18n.t('font_size')} (px)")
        self.lang_label.setText(i18n.t("language"))
        self.preview_label.setText(i18n.t("preview"))
        self.hint_label.setText(i18n.t("settings_hint"))
        self.reset_btn.setText(i18n.t("reset_firewall_tip"))
        for button in self.findChildren(QPushButton):
            if button is self.reset_btn:
                continue
            button.setText(i18n.t("close"))
        current = self.controller.i18n.language
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        for _label, code in LANGUAGES:
            text = i18n.t("chinese") if code == "zh" else i18n.t("english")
            self.lang_combo.addItem(text, code)
        index = self.lang_combo.findData(current)
        self.lang_combo.setCurrentIndex(index if index >= 0 else 0)
        self.lang_combo.blockSignals(False)

    def _apply(self, *_args) -> None:
        self.controller.apply_settings(
            font_family=self.font_combo.currentFont().family(),
            font_size=self.size_spin.value(),
            language=self.lang_combo.currentData() or "zh",
        )
        self._retranslate()


class UploadRow(QFrame):
    def __init__(self, folder: UploadFolder, controller: "MainWindow") -> None:
        super().__init__()
        self.folder = folder
        self.controller = controller
        self.setObjectName("shareRow")
        self.set_selected(False)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        badge = QLabel(controller.text("folder"), objectName="typeBadge")
        badge.setProperty("kind", "directory")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumWidth(58)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(folder.name, objectName="shareName")
        path = QLabel(_elide(folder.path, 66), objectName="sharePath")
        path.setToolTip(folder.path)
        link = QLabel(_elide(controller.upload_url(folder), 66), objectName="shareLink")
        link.setToolTip(controller.upload_url(folder))
        info.addWidget(name)
        info.addWidget(path)
        info.addWidget(link)
        if not Path(folder.path).exists():
            info.addWidget(QLabel(controller.text("missing_path"), objectName="missingBadge"))
        root.addLayout(info, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        copy_btn = QPushButton(controller.text("copy_link"), objectName="rowPrimary")
        copy_btn.clicked.connect(lambda: controller.copy_upload_link(folder.token))
        qr_btn = QPushButton(controller.text("qr_code"), objectName="rowButton")
        qr_btn.clicked.connect(lambda: controller.show_upload_qr(folder.token))
        open_btn = QPushButton(controller.text("open_upload_page"), objectName="rowButton")
        open_btn.clicked.connect(lambda: controller.open_upload_page(folder.token))
        remove_btn = QPushButton(controller.text("remove"), objectName="rowDanger")
        remove_btn.clicked.connect(lambda: controller.remove_upload_token(folder.token))
        buttons.addWidget(copy_btn)
        buttons.addWidget(qr_btn)
        buttons.addWidget(open_btn)
        buttons.addWidget(remove_btn)
        root.addLayout(buttons)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setHeight(max(78, self.controller.font_size * 5 + 22))
        return hint


class UploadFolderDialog(QDialog):
    def __init__(self, controller: "MainWindow", i18n: Translator) -> None:
        super().__init__(controller)
        prepare_light_window(self)
        self.controller = controller
        self.i18n = i18n
        self.setWindowTitle(i18n.t("upload_folder_dialog_title"))
        self.setMinimumWidth(470)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(i18n.t("upload_folder_name"))
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText(i18n.t("target_path"))
        browse_btn = QPushButton(i18n.t("browse"), objectName="rowButton")
        browse_btn.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_btn)

        form.addRow(i18n.t("upload_folder_name"), self.name_edit)
        form.addRow(i18n.t("target_path"), path_row)
        root.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_btn = QPushButton(i18n.t("firewall_cancel"))
        cancel_btn.clicked.connect(self.reject)
        add_btn = QPushButton(i18n.t("add_upload_folder"), objectName="primaryButton")
        add_btn.clicked.connect(self.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(add_btn)
        root.addLayout(actions)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            self.i18n.t("select_upload_folder_title"),
            "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.path_edit.setText(path)
            if not self.name_edit.text().strip():
                self.name_edit.setText(Path(path).name)

    def accept(self) -> None:
        name = self.name_edit.text().strip()
        raw_path = self.path_edit.text().strip()
        if not name:
            self.controller._show_warning(self.i18n.t("upload_folder_error_title"), self.i18n.t("upload_name_required"))
            return
        if len(name) > 60 or "/" in name or "\\" in name:
            self.controller._show_warning(self.i18n.t("upload_folder_error_title"), self.i18n.t("upload_name_invalid"))
            return
        if not raw_path:
            self.controller._show_warning(self.i18n.t("upload_folder_error_title"), self.i18n.t("upload_path_required"))
            return
        path = Path(raw_path).expanduser()
        if not path.is_dir():
            self.controller._show_warning(self.i18n.t("upload_folder_error_title"), self.i18n.t("upload_path_invalid"))
            return
        resolved = str(path.resolve())
        if any(item.path == resolved for item in self.controller.upload_registry.all()):
            self.controller._show_warning(self.i18n.t("upload_folder_error_title"), self.i18n.t("upload_duplicate_path"))
            return
        super().accept()

    def data(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self.path_edit.text().strip()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        force_light_title_bar(self)


class QRCodeDialog(QDialog):
    def __init__(
        self,
        link: str,
        share: Share | UploadFolder,
        i18n: Translator,
        parent: QWidget | None = None,
        title_key: str = "qr_suffix",
    ) -> None:
        super().__init__(parent)
        prepare_light_window(self)
        self.setWindowTitle(i18n.t("qr_title"))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        display_name = getattr(share, "name", Path(share.path).name)
        title = QLabel(i18n.t(title_key, name=display_name))
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont(QApplication.font().family(), 12, QFont.Bold))
        layout.addWidget(title)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumHeight(300)
        try:
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(link)
            qr.make(fit=True)
            image = qr.make_image(fill_color="#111827", back_color="#ffffff").convert("RGB")
            data = image.tobytes("raw", "RGB")
            qimage = QImage(
                data,
                image.width,
                image.height,
                3 * image.width,
                QImage.Format.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(qimage).scaled(
                290, 290, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            image_label.setPixmap(pixmap)
        except Exception as exc:
            image_label.setText(i18n.t("qr_failed", error=exc))
        layout.addWidget(image_label)

        link_edit = QLineEdit(link, objectName="qrLink")
        link_edit.setReadOnly(True)
        link_edit.setCursorPosition(0)
        layout.addWidget(link_edit)

        actions = QHBoxLayout()
        actions.addStretch(1)
        copy_btn = QPushButton(i18n.t("copy_link"))
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(link))
        close_btn = QPushButton(i18n.t("close"), objectName="primaryButton")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(copy_btn)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        force_light_title_bar(self)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        prepare_light_window(self)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(make_light_palette())
            self._light_filter = LightTitleBarFilter(self)
            app.installEventFilter(self._light_filter)
        self.config = load_config()
        self.registry = ShareRegistry()
        self.registry.load_from_config(self.config.get("shares", []))
        self.upload_registry = UploadRegistry()
        self.upload_registry.load_from_config(self.config.get("uploads", []))

        self.font_family = str(self.config.get("font_family", "Microsoft YaHei UI"))
        self.font_size = int(self.config.get("font_size", 13))
        self.i18n = Translator(str(self.config.get("language", "zh")))
        self.server: LanHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self._stopping = False
        self.log_queue: queue.Queue[tuple[str, str, str]] = queue.Queue()

        self.setWindowTitle(self.text("app_title"))
        self.resize(1060, 720)
        self.setMinimumSize(940, 640)
        self.setAcceptDrops(True)
        self.apply_visual_settings()
        self._build_ui()
        self.retranslate_ui()
        self._load_saved_config()
        self._refresh_share_list()
        self._refresh_upload_list()
        self._update_running_ui()
        self._push_log(self.text("log_ready"))

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_events)
        self.poll_timer.start(400)

    # ---------------------------------------------------------------- 通用
    def text(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def _show_warning(self, title: str, message: str) -> None:
        box = LightMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()

    def apply_visual_settings(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.setFont(QFont(self.font_family, self.font_size))
        app.setStyleSheet(build_stylesheet(self.font_family, self.font_size))

    def apply_settings(
        self,
        font_family: str | None = None,
        font_size: int | None = None,
        language: str | None = None,
        show_status: bool = False,
    ) -> None:
        if font_family:
            self.font_family = font_family
        if font_size:
            self.font_size = max(9, min(22, int(font_size)))
        if language:
            self.i18n.language = "en" if language.startswith("en") else "zh"
        self.apply_visual_settings()
        self.retranslate_ui()
        if self.server:
            self.server.language = self.i18n.language
        self.save_config_now()
        if show_status:
            self.statusBar().showMessage(self.text("status_settings_saved"), 3000)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, self.i18n)
        dialog.exec()

    def reset_firewall_notice(self) -> None:
        self.config["firewall_notice_shown"] = False
        self.save_config_now()
        self.statusBar().showMessage(self.text("status_firewall_reset"), 4000)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.text("app_title"))
        self.title_label.setText(self.text("app_title"))
        self.subtitle_label.setText(self.text("app_subtitle"))
        self.settings_btn.setText(self.text("settings"))
        self.server_title.setText(self.text("server_title"))
        self.server_subtitle.setText(self.text("server_subtitle"))
        self.ip_label.setText(self.text("listen_ip"))
        self.port_label.setText(self.text("port"))
        self.base_label.setText(self.text("request_path"))
        self.refresh_ip_btn.setText(self.text("refresh"))
        self.refresh_ip_btn.setToolTip(self.text("refresh_tip"))
        self.path_hint.setText(self.text("path_hint"))
        self.start_btn.setText(self.text("start_service"))
        self.stop_btn.setText(self.text("stop_service"))
        self.open_link_btn.setText(self.text("open_service_url"))
        self.info_status_label.setText(self.text("info_status"))
        self.info_url_label.setText(self.text("info_url"))
        self.info_requests_label.setText(self.text("info_requests"))
        self.share_title.setText(self.text("share_title"))
        self.add_file_btn.setText(self.text("add_file"))
        self.add_folder_btn.setText(self.text("add_folder"))
        self.remove_selected_btn.setText(self.text("remove_selected"))
        self.drop_area.retranslate(self.i18n)
        self.empty_hint.setText(self.text("empty_share"))
        self.right_tabs.setTabText(0, self.text("share_title"))
        self.right_tabs.setTabText(1, self.text("upload_title"))
        self.upload_title.setText(self.text("upload_title"))
        self.upload_subtitle.setText(self.text("upload_subtitle"))
        self.add_upload_btn.setText(self.text("add_upload_folder"))
        self.remove_upload_selected_btn.setText(self.text("remove_selected"))
        self.upload_empty_hint.setText(self.text("upload_empty"))
        self.log_title.setText(self.text("log_title"))
        self.clear_log_btn.setText(self.text("clear"))
        self._update_running_ui()
        self._refresh_share_list()
        self._refresh_upload_list()

    # ---------------------------------------------------------------- 构建界面
    def _build_ui(self) -> None:
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(16)
        root.addWidget(self._build_header())

        content = QHBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._build_server_card(), 0)
        content.addWidget(self._build_right_tabs(), 1)
        root.addLayout(content, 1)
        root.addWidget(self._build_log_card(), 0)

        self.ip_combo.currentIndexChanged.connect(self._on_server_config_changed)
        self.port_input.valueChanged.connect(self._on_server_config_changed)
        self.base_input.textChanged.connect(self._on_server_config_changed)

    def _on_server_config_changed(self, *_args) -> None:
        self.save_config_now()
        self._refresh_share_list()
        self._refresh_upload_list()

    def _build_right_tabs(self) -> QWidget:
        self.right_tabs = QTabWidget()
        self.right_tabs.addTab(self._build_share_card(), self.text("share_title"))
        self.right_tabs.addTab(self._build_upload_card(), self.text("upload_title"))
        return self.right_tabs

    def _build_header(self) -> QWidget:
        header = QFrame(objectName="header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 0, 2, 0)
        left = QVBoxLayout()
        left.setSpacing(3)
        self.title_label = QLabel(objectName="appTitle")
        self.subtitle_label = QLabel(objectName="appSubtitle")
        left.addWidget(self.title_label)
        left.addWidget(self.subtitle_label)
        layout.addLayout(left)
        layout.addStretch(1)
        self.status_badge = QLabel(objectName="statusBadge")
        self.status_badge.setProperty("state", "stopped")
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.settings_btn = QPushButton()
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.status_badge)
        layout.addWidget(self.settings_btn)
        return header

    def _build_server_card(self) -> QWidget:
        card = QFrame(objectName="card")
        card.setMinimumWidth(320)
        card.setMaximumWidth(380)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(14)

        self.server_title = QLabel(objectName="sectionTitle")
        self.server_subtitle = QLabel(objectName="sectionSubtitle")
        layout.addWidget(self.server_title)
        layout.addWidget(self.server_subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        ip_row = QHBoxLayout()
        ip_row.setSpacing(6)
        self.ip_combo = QComboBox()
        self.ip_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.ip_combo.setFixedHeight(36)
        self.refresh_ip_btn = QPushButton(objectName="refreshButton")
        self.refresh_ip_btn.setFixedHeight(36)
        self.refresh_ip_btn.clicked.connect(lambda: self.refresh_interfaces())
        ip_row.addWidget(self.ip_combo, 1)
        ip_row.addWidget(self.refresh_ip_btn)

        self.ip_label = QLabel()
        self.port_label = QLabel()
        self.base_label = QLabel()
        form.addRow(self.ip_label, ip_row)

        self.port_input = NumberEdit(1, 65535, 8765)
        self.port_input.setFixedHeight(36)
        form.addRow(self.port_label, self.port_input)

        self.base_input = QLineEdit()
        self.base_input.setPlaceholderText("/share")
        self.base_input.setFixedHeight(36)
        form.addRow(self.base_label, self.base_input)
        layout.addLayout(form)

        self.path_hint = QLabel(objectName="hint")
        self.path_hint.setWordWrap(True)
        layout.addWidget(self.path_hint)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.start_btn = QPushButton(objectName="primaryButton")
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn = QPushButton()
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        actions.addWidget(self.start_btn, 1)
        actions.addWidget(self.stop_btn, 1)
        layout.addLayout(actions)

        self.open_link_btn = QPushButton()
        self.open_link_btn.setEnabled(False)
        self.open_link_btn.clicked.connect(self.open_service_url)
        layout.addWidget(self.open_link_btn)

        info = QFrame(objectName="infoBox")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(7)

        self.info_status_label = QLabel(objectName="infoKey")
        self.status_detail = QLabel(objectName="infoValue")
        row1 = QHBoxLayout()
        row1.addWidget(self.info_status_label)
        row1.addWidget(self.status_detail, 1)
        info_layout.addLayout(row1)

        self.info_url_label = QLabel(objectName="infoKey")
        self.url_detail = QLabel("-", objectName="infoValueLink")
        self.url_detail.setWordWrap(True)
        self.url_detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row2 = QHBoxLayout()
        row2.addWidget(self.info_url_label)
        row2.addWidget(self.url_detail, 1)
        info_layout.addLayout(row2)

        self.info_requests_label = QLabel(objectName="infoKey")
        self.requests_detail = QLabel("0", objectName="infoValue")
        row3 = QHBoxLayout()
        row3.addWidget(self.info_requests_label)
        row3.addWidget(self.requests_detail, 1)
        info_layout.addLayout(row3)
        layout.addWidget(info)
        layout.addStretch(1)
        return card

    def _build_share_card(self) -> QWidget:
        card = QFrame(objectName="card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        self.share_title = QLabel(objectName="sectionTitle")
        self.count_badge = QLabel(objectName="countBadge")
        title_row.addWidget(self.share_title)
        title_row.addWidget(self.count_badge)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.add_file_btn = QPushButton()
        self.add_file_btn.clicked.connect(self.add_files)
        self.add_folder_btn = QPushButton()
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.remove_selected_btn = QPushButton(objectName="dangerButton")
        self.remove_selected_btn.clicked.connect(self.remove_selected)
        toolbar.addWidget(self.add_file_btn)
        toolbar.addWidget(self.add_folder_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.remove_selected_btn)
        layout.addLayout(toolbar)

        self.drop_area = DropArea()
        self.drop_area.filesDropped.connect(self.add_paths)
        layout.addWidget(self.drop_area)

        self.share_list = QListWidget(objectName="shareList")
        self.share_list.setFrameShape(QFrame.NoFrame)
        self.share_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.share_list.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.share_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.share_list.setAcceptDrops(False)
        self.share_list.itemSelectionChanged.connect(self._sync_row_selection)
        self.share_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.share_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.share_list, 1)

        self.empty_hint = QLabel(objectName="emptyHint")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_hint, 1)
        return card

    def _build_upload_card(self) -> QWidget:
        card = QFrame(objectName="card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        self.upload_title = QLabel(objectName="sectionTitle")
        self.upload_count_badge = QLabel(objectName="countBadge")
        title_row.addWidget(self.upload_title)
        title_row.addWidget(self.upload_count_badge)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        subtitle = QLabel(self.text("upload_subtitle"), objectName="sectionSubtitle")
        self.upload_subtitle = subtitle
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.add_upload_btn = QPushButton()
        self.add_upload_btn.clicked.connect(self.add_upload_folder)
        self.remove_upload_selected_btn = QPushButton(objectName="dangerButton")
        self.remove_upload_selected_btn.clicked.connect(self.remove_selected_uploads)
        toolbar.addWidget(self.add_upload_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.remove_upload_selected_btn)
        layout.addLayout(toolbar)

        self.upload_list = QListWidget(objectName="shareList")
        self.upload_list.setFrameShape(QFrame.NoFrame)
        self.upload_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.upload_list.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.upload_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.upload_list.itemSelectionChanged.connect(self._sync_upload_row_selection)
        self.upload_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.upload_list.customContextMenuRequested.connect(self._show_upload_context_menu)
        layout.addWidget(self.upload_list, 1)

        self.upload_empty_hint = QLabel(objectName="emptyHint")
        self.upload_empty_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.upload_empty_hint, 1)
        return card

    def _build_log_card(self) -> QWidget:
        card = QFrame(objectName="logCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        row = QHBoxLayout()
        self.log_title = QLabel(objectName="sectionTitle")
        self.clear_log_btn = QPushButton(objectName="rowButton")
        self.clear_log_btn.clicked.connect(lambda: self.log_view.clear())
        row.addWidget(self.log_title)
        row.addStretch(1)
        row.addWidget(self.clear_log_btn)
        layout.addLayout(row)
        self.log_view = QPlainTextEdit(objectName="logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(104)
        layout.addWidget(self.log_view)
        return card

    # ---------------------------------------------------------------- 配置与状态
    def _load_saved_config(self) -> None:
        self.port_input.setValue(int(self.config.get("port", 8765)))
        self.base_input.setText(str(self.config.get("base_path", "/share")))
        self.refresh_interfaces(preferred=str(self.config.get("bind_ip", "0.0.0.0")))

    def refresh_interfaces(self, preferred: str | None = None) -> None:
        addresses = list_bind_addresses()
        current = preferred if preferred is not None else self.ip_combo.currentData()
        current = current or "0.0.0.0"
        if current != "0.0.0.0" and not any(ip == current for _, ip in addresses):
            addresses.insert(1, (self.text("saved_address", ip=current), current))
        self.ip_combo.clear()
        for label, ip in addresses:
            self.ip_combo.addItem(label, ip)
        index = self.ip_combo.findData(current)
        self.ip_combo.setCurrentIndex(index if index >= 0 else 0)
        if preferred is None:
            self.save_config_now()

    def current_config(self) -> dict:
        return {
            "bind_ip": self.ip_combo.currentData() or "0.0.0.0",
            "port": self.port_input.value(),
            "base_path": normalize_base_path(self.base_input.text()),
            "shares": self.registry.to_config(),
            "uploads": self.upload_registry.to_config(),
            "font_family": self.font_family,
            "font_size": self.font_size,
            "language": self.i18n.language,
            "firewall_notice_shown": bool(self.config.get("firewall_notice_shown", False)),
        }

    def save_config_now(self) -> None:
        try:
            save_config(self.current_config())
        except OSError as exc:
            self._push_log(self.text("log_config_failed", error=exc), "error")

    def _update_running_ui(self) -> None:
        running = self.is_running()
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.ip_combo.setEnabled(not running)
        self.refresh_ip_btn.setEnabled(not running)
        self.port_input.setEnabled(not running)
        self.base_input.setEnabled(not running)
        self.open_link_btn.setEnabled(running)
        self.status_badge.setText(self.text("status_running" if running else "status_stopped"))
        self.status_badge.setProperty("state", "running" if running else "stopped")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)
        if running:
            self.status_detail.setText(
                self.text(
                    "running_at",
                    ip=self.ip_combo.currentData(),
                    port=self.port_input.value(),
                )
            )
            self.url_detail.setText(self.service_url())
            self.requests_detail.setText(str(self.server.request_count if self.server else 0))
        else:
            self.status_detail.setText(self.text("not_started"))
            self.url_detail.setText("-")
            self.requests_detail.setText("0")

    def is_running(self) -> bool:
        return self.server is not None and self.server_thread is not None and self.server_thread.is_alive()

    def service_url(self) -> str:
        bind_ip = self.ip_combo.currentData() or "0.0.0.0"
        host = lan_ip() if bind_ip == "0.0.0.0" else bind_ip
        base = normalize_base_path(self.base_input.text())
        prefix = "" if base == "/" else base
        return f"http://{host}:{self.port_input.value()}{prefix}/"

    def share_url(self, share: Share) -> str:
        bind_ip = self.ip_combo.currentData() or "0.0.0.0"
        host = lan_ip() if bind_ip == "0.0.0.0" else bind_ip
        base = normalize_base_path(self.base_input.text())
        prefix = "" if base == "/" else base
        route = "d" if share.kind == "file" else "s"
        return f"http://{host}:{self.port_input.value()}{prefix}/{route}/{quote(share.token, safe='')}"

    def upload_url(self, folder: UploadFolder) -> str:
        bind_ip = self.ip_combo.currentData() or "0.0.0.0"
        host = lan_ip() if bind_ip == "0.0.0.0" else bind_ip
        base = normalize_base_path(self.base_input.text())
        prefix = "" if base == "/" else base
        return f"http://{host}:{self.port_input.value()}{prefix}/u/{quote(folder.token, safe='')}"

    def _validate_base_path(self) -> str:
        raw = self.base_input.text().strip() or "/"
        if not raw.startswith("/"):
            raw = "/" + raw
        if any(char in raw for char in "?# \t\r\n\\"):
            raise ValueError(self.text("invalid_path_space"))
        base = normalize_base_path(raw)
        if not re.fullmatch(r"/[A-Za-z0-9._~\-\u4e00-\u9fff/]*", base):
            raise ValueError(self.text("invalid_path_chars"))
        return base

    # ---------------------------------------------------------------- 服务控制
    def _confirm_firewall_notice_once(self) -> bool:
        if self.config.get("firewall_notice_shown"):
            return True
        dialog = FirewallNoticeDialog(self.i18n, self)
        if dialog.exec() != QDialog.Accepted:
            return False
        self.config["firewall_notice_shown"] = True
        self.save_config_now()
        return True

    def start_server(self) -> None:
        if self.is_running():
            return
        try:
            base = self._validate_base_path()
        except ValueError as exc:
            self._show_warning(self.text("invalid_path_title"), str(exc))
            return
        if not self._confirm_firewall_notice_once():
            return
        self.base_input.setText(base)
        ip = self.ip_combo.currentData() or "0.0.0.0"
        port = self.port_input.value()
        self.save_config_now()

        try:
            server = LanHTTPServer(
                (ip, port),
                ShareRequestHandler,
                self.registry,
                self.upload_registry,
                base,
                self._push_log,
                language=self.i18n.language,
            )
        except OSError as exc:
            self._show_warning(
                self.text("start_failed_title"),
                self.text("start_failed_msg", ip=ip, port=port, error=exc),
            )
            self._push_log(self.text("log_start_failed", error=exc), "error")
            return

        self.server = server
        self.server_thread = threading.Thread(
            target=self._serve_forever,
            args=(server,),
            name="LanFileShareHTTP",
            daemon=True,
        )
        self.server_thread.start()
        self._push_log(self.text("log_started", url=self.service_url()))
        self._update_running_ui()

    def _serve_forever(self, server: LanHTTPServer) -> None:
        try:
            server.serve_forever(poll_interval=0.2)
        except Exception as exc:
            self._push_log(self.text("log_service_error", error=exc), "error")

    def stop_server(self) -> None:
        if not self.server or self._stopping:
            return
        self._stopping = True
        server = self.server
        thread = self.server_thread
        try:
            server.shutdown()
            server.server_close()
            if thread and thread.is_alive():
                thread.join(timeout=2)
        except Exception as exc:
            self._push_log(self.text("log_stop_error", error=exc), "error")
        finally:
            self.server = None
            self.server_thread = None
            self._stopping = False
            self._push_log(self.text("log_stopped"))
            self._update_running_ui()

    def open_service_url(self) -> None:
        QDesktopServices.openUrl(QUrl(self.service_url()))

    # ---------------------------------------------------------------- 分享操作
    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.text("select_files_title"),
            "",
            self.text("select_files_filter"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if paths:
            self.add_paths(paths)

    def add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            self.text("select_folder_title"),
            "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.add_paths([path])

    def add_paths(self, paths: Iterable[str]) -> None:
        existing = {share.token for share in self.registry.all()}
        added = 0
        skipped = 0
        for raw in paths:
            path = Path(raw).expanduser()
            if not path.exists():
                skipped += 1
                self._push_log(self.text("log_path_missing", path=raw), "warn")
                continue
            share = self.registry.add(path)
            if share.token in existing:
                skipped += 1
                continue
            existing.add(share.token)
            added += 1
            self._push_log(
                self.text("log_added", name=path.name, url=self.share_url(share))
            )
        if added:
            self.save_config_now()
            self._refresh_share_list()
            self.statusBar().showMessage(self.text("status_added", count=added), 4000)
        elif skipped:
            self.statusBar().showMessage(self.text("status_duplicate"), 4000)

    def remove_token(self, token: str) -> None:
        share = self.registry.remove(token)
        if not share:
            return
        self.save_config_now()
        self._refresh_share_list()
        self._push_log(self.text("log_removed", name=Path(share.path).name))
        self.statusBar().showMessage(self.text("status_removed"), 3000)

    def remove_selected(self) -> None:
        tokens = [item.data(Qt.UserRole) for item in self.share_list.selectedItems()]
        if not tokens:
            self.statusBar().showMessage(self.text("status_select_first"), 3000)
            return
        for token in tokens:
            self.registry.remove(token)
        self.save_config_now()
        self._refresh_share_list()
        self._push_log(self.text("log_removed_many", count=len(tokens)))
        self.statusBar().showMessage(self.text("status_removed_many", count=len(tokens)), 3000)

    def copy_link(self, token: str) -> None:
        share = self.registry.get(token)
        if not share:
            return
        link = self.share_url(share)
        QGuiApplication.clipboard().setText(link)
        self._push_log(self.text("log_copy_link", url=link))
        self.statusBar().showMessage(self.text("status_link_copied"), 3000)

    def show_qr(self, token: str) -> None:
        share = self.registry.get(token)
        if not share:
            return
        dialog = QRCodeDialog(self.share_url(share), share, self.i18n, self)
        dialog.exec()

    def open_share_path(self, token: str) -> None:
        share = self.registry.get(token)
        if not share:
            return
        path = Path(share.path)
        target = path if path.is_dir() else path.parent
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    # ---------------------------------------------------------------- 上传管理
    def add_upload_folder(self) -> None:
        dialog = UploadFolderDialog(self, self.i18n)
        if dialog.exec() != QDialog.Accepted:
            return
        name, path = dialog.data()
        existing = self.upload_registry.all()
        folder = self.upload_registry.add(name, path)
        if folder in existing:
            self.statusBar().showMessage(self.text("upload_duplicate_path"), 4000)
            return
        self.save_config_now()
        self._refresh_upload_list()
        self._push_log(
            self.text("log_upload_added", name=folder.name, url=self.upload_url(folder))
        )
        self.statusBar().showMessage(self.text("items_count", count=self.upload_registry.count()), 4000)

    def remove_upload_token(self, token: str) -> None:
        folder = self.upload_registry.remove(token)
        if not folder:
            return
        self.save_config_now()
        self._refresh_upload_list()
        self._push_log(self.text("log_upload_removed", name=folder.name))
        self.statusBar().showMessage(self.text("status_upload_removed"), 3000)

    def remove_selected_uploads(self) -> None:
        tokens = [item.data(Qt.UserRole) for item in self.upload_list.selectedItems()]
        if not tokens:
            self.statusBar().showMessage(self.text("status_upload_select_first"), 3000)
            return
        for token in tokens:
            self.upload_registry.remove(token)
        self.save_config_now()
        self._refresh_upload_list()
        self._push_log(self.text("log_upload_removed", name=str(len(tokens))))
        self.statusBar().showMessage(self.text("status_upload_removed"), 3000)

    def copy_upload_link(self, token: str) -> None:
        folder = self.upload_registry.get(token)
        if not folder:
            return
        link = self.upload_url(folder)
        QGuiApplication.clipboard().setText(link)
        self._push_log(self.text("log_copy_link", url=link))
        self.statusBar().showMessage(self.text("status_link_copied"), 3000)

    def show_upload_qr(self, token: str) -> None:
        folder = self.upload_registry.get(token)
        if not folder:
            return
        link = self.upload_url(folder)
        dialog = QRCodeDialog(link, folder, self.i18n, self, title_key="upload_qr_suffix")
        dialog.exec()

    def open_upload_page(self, token: str) -> None:
        folder = self.upload_registry.get(token)
        if folder:
            QDesktopServices.openUrl(QUrl(self.upload_url(folder)))

    def _show_upload_context_menu(self, position) -> None:
        item = self.upload_list.itemAt(position)
        if not item:
            return
        token = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction(self.text("copy_link"), lambda: self.copy_upload_link(token))
        menu.addAction(self.text("qr_code"), lambda: self.show_upload_qr(token))
        menu.addAction(self.text("open_upload_page"), lambda: self.open_upload_page(token))
        menu.addSeparator()
        menu.addAction(self.text("remove"), lambda: self.remove_upload_token(token))
        menu.exec(self.upload_list.viewport().mapToGlobal(position))

    def _refresh_upload_list(self) -> None:
        self.upload_list.clear()
        folders = self.upload_registry.all()
        for folder in folders:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, folder.token)
            item.setSizeHint(self._row_size())
            self.upload_list.addItem(item)
            self.upload_list.setItemWidget(item, UploadRow(folder, self))
        self.upload_count_badge.setText(self.text("upload_items_count", count=len(folders)))
        empty = len(folders) == 0
        self.upload_empty_hint.setVisible(empty)
        self.upload_list.setVisible(not empty)
        self.remove_upload_selected_btn.setEnabled(not empty)
        self._sync_upload_row_selection()

    def _sync_upload_row_selection(self) -> None:
        selected = {item.data(Qt.UserRole) for item in self.upload_list.selectedItems()}
        for index in range(self.upload_list.count()):
            item = self.upload_list.item(index)
            widget = self.upload_list.itemWidget(item)
            if isinstance(widget, UploadRow):
                widget.set_selected(item.data(Qt.UserRole) in selected)

    def _show_context_menu(self, position) -> None:
        item = self.share_list.itemAt(position)
        if not item:
            return
        token = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction(self.text("copy_link"), lambda: self.copy_link(token))
        menu.addAction(self.text("qr_code"), lambda: self.show_qr(token))
        menu.addAction(self.text("open_folder"), lambda: self.open_share_path(token))
        menu.addSeparator()
        menu.addAction(self.text("remove"), lambda: self.remove_token(token))
        menu.exec(self.share_list.viewport().mapToGlobal(position))

    def _refresh_share_list(self) -> None:
        self.share_list.clear()
        shares = self.registry.all()
        for share in shares:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, share.token)
            item.setSizeHint(self._row_size())
            self.share_list.addItem(item)
            self.share_list.setItemWidget(item, ShareRow(share, self))
        self.count_badge.setText(self.text("items_count", count=len(shares)))
        empty = len(shares) == 0
        self.empty_hint.setVisible(empty)
        self.share_list.setVisible(not empty)
        self.remove_selected_btn.setEnabled(not empty)
        self._sync_row_selection()

    def _row_size(self) -> QSize:
        return QSize(10, max(78, self.font_size * 5 + 22))

    def _sync_row_selection(self) -> None:
        selected = {item.data(Qt.UserRole) for item in self.share_list.selectedItems()}
        for index in range(self.share_list.count()):
            item = self.share_list.item(index)
            widget = self.share_list.itemWidget(item)
            if isinstance(widget, ShareRow):
                widget.set_selected(item.data(Qt.UserRole) in selected)

    # ---------------------------------------------------------------- 拖放与日志
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_area.set_active(True)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.drop_area.set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.drop_area.set_active(False)
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.add_paths(paths)
        else:
            super().dropEvent(event)

    def _push_log(self, message: str, level: str = "info") -> None:
        self.log_queue.put((time.strftime("%H:%M:%S"), level, str(message)))

    def _poll_events(self) -> None:
        lines: List[str] = []
        while True:
            try:
                stamp, level, message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            prefix = {
                "warn": self.text("log_warn"),
                "error": self.text("log_error"),
            }.get(level, "")
            lines.append(f"{stamp} {prefix}{message}".rstrip())
        if lines:
            all_lines = (self.log_view.toPlainText() + "\n" + "\n".join(lines)).splitlines()
            self.log_view.setPlainText("\n".join(all_lines[-300:]))
            self.log_view.moveCursor(QTextCursor.End)
        if self.server:
            self.requests_detail.setText(str(self.server.request_count))

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        force_light_title_bar(self)

    def closeEvent(self, event) -> None:
        self.save_config_now()
        if self.server:
            self.stop_server()
        super().closeEvent(event)
