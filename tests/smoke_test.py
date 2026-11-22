"""本地冒烟测试：HTTP 路由、下载、目录浏览、配置与界面初始化。"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TEMP_ROOT = tempfile.mkdtemp(prefix="lanfileshare-test-")
os.environ["APPDATA"] = TEMP_ROOT
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import config_path, load_config  # noqa: E402
from app.registry import ShareRegistry, UploadRegistry  # noqa: E402
from app.server import LanHTTPServer, ShareRequestHandler  # noqa: E402
from app.ui import FirewallNoticeDialog, MainWindow, QRCodeDialog, SettingsDialog  # noqa: E402


def fetch(url: str, method: str = "GET", headers: dict | None = None):
    request = Request(url, method=method, headers=headers or {})
    with urlopen(request, timeout=5) as response:
        return response.status, dict(response.headers), response.read()


def post_upload(url: str, filename: str, content: bytes):
    boundary = "----lanfileshare-test-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlopen(request, timeout=5) as response:
        return response.status, response.read()


def expect_status(url: str, status: int, method: str = "GET", headers: dict | None = None):
    try:
        actual, response_headers, body = fetch(url, method, headers)
    except HTTPError as exc:
        actual, response_headers, body = exc.code, dict(exc.headers), exc.read()
    assert actual == status, f"{url} expected {status}, got {actual}"
    return response_headers, body


def main() -> None:
    base = Path(TEMP_ROOT)
    shared = base / "shared"
    (shared / "sub").mkdir(parents=True)
    (shared / "hello.txt").write_text("ABCDEFGHIJ", encoding="utf-8")
    (shared / "sub" / "nested.txt").write_text("nested content", encoding="utf-8")
    (base / "secret.txt").write_text("private", encoding="utf-8")

    registry = ShareRegistry()
    file_share = registry.add(shared / "hello.txt")
    dir_share = registry.add(shared)
    upload_root = base / "incoming"
    upload_root.mkdir()
    uploads = UploadRegistry()
    upload_folder = uploads.add("收件箱", upload_root)

    server = LanHTTPServer(
        ("127.0.0.1", 0),
        ShareRequestHandler,
        registry,
        uploads,
        "/share",
        lambda message: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{server.server_address[1]}/share"

    _, _, health = fetch(f"{root}/health")
    assert json.loads(health)["status"] == "running"

    _, headers, body = fetch(f"{root}/d/{file_share.token}")
    assert body == b"ABCDEFGHIJ"
    assert "attachment" in headers["Content-Disposition"]

    _, headers, body = fetch(
        f"{root}/d/{file_share.token}", headers={"Range": "bytes=2-4"}
    )
    assert headers["Content-Range"].startswith("bytes 2-4/")
    assert body == b"CDE"

    _, _, listing = fetch(f"{root}/s/{dir_share.token}")
    html = listing.decode("utf-8")
    assert "hello.txt" in html and "sub" in html and "下载" in html

    server.language = "en"
    _, _, en_listing = fetch(f"{root}/s/{dir_share.token}")
    en_html = en_listing.decode("utf-8")
    assert "Download" in en_html and "Name" in en_html
    server.language = "zh"

    _, _, nested = fetch(f"{root}/s/{dir_share.token}/sub/nested.txt")
    assert nested == b"nested content"

    expect_status(f"{root}/s/{dir_share.token}/../secret.txt", 403)
    expect_status(f"{root}/unknown", 404)
    expect_status(f"{root}/d/missing-token", 404)

    request = Request(f"{root}/d/{file_share.token}", method="HEAD")
    with urlopen(request, timeout=5) as response:
        assert response.headers["Content-Length"] == "10"
        assert response.read() == b""

    _, _, upload_page = fetch(f"{root}/u/{upload_folder.token}")
    upload_html = upload_page.decode("utf-8")
    assert "multipart/form-data" in upload_html and "收件箱" in upload_html

    status, result_page = post_upload(
        f"{root}/u/{upload_folder.token}", "note.txt", b"uploaded content"
    )
    assert status == 200
    assert (upload_root / "note.txt").read_bytes() == b"uploaded content"
    assert "成功上传 1 个文件" in result_page.decode("utf-8")

    post_upload(f"{root}/u/{upload_folder.token}", "../escaped.txt", b"safe")
    assert not (base / "escaped.txt").exists()
    assert (upload_root / "escaped.txt").read_bytes() == b"safe"

    expect_status(f"{root}/u/invalid-token", 404)
    try:
        request = Request(f"{root}/u/{upload_folder.token}", data=b"plain", method="POST")
        urlopen(request, timeout=5)
        raise AssertionError("non-multipart upload should fail")
    except HTTPError as exc:
        assert exc.code == 400

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.title_label.text() == "局域网文件分享"

    window.port_input.setText("54321")
    assert window.port_input.value() == 54321
    settings = SettingsDialog(window, window.i18n)
    settings.size_spin.setText("18")
    assert settings.size_spin.value() == 18

    window.apply_settings(font_family="Arial", font_size=16, language="en")
    assert window.title_label.text() == "LAN File Share"
    assert window.text("start_service") == "Start service"
    en_settings = load_config()
    assert en_settings["font_family"] == "Arial"
    assert en_settings["font_size"] == 16
    assert en_settings["language"] == "en"

    window.apply_settings(font_family="Microsoft YaHei UI", font_size=13, language="zh")
    assert window.title_label.text() == "局域网文件分享"

    notice = FirewallNoticeDialog(window.i18n, window)
    assert "防火墙" in notice.windowTitle()
    assert not notice.continue_btn.isEnabled()
    notice.ack_box.setChecked(True)
    assert notice.continue_btn.isEnabled()

    window.ip_combo.setCurrentIndex(window.ip_combo.findData("127.0.0.1"))
    window.port_input.setValue(9876)
    window.base_input.setText("/share")
    assert window.registry.count() == 0
    window.add_paths([str(shared / "hello.txt"), str(shared)])
    assert window.registry.count() == 2
    assert "/share/d/" in window.share_url(window.registry.all()[0])
    window.upload_registry.add("界面上传", upload_root)
    assert window.upload_registry.count() == 1
    assert "/share/u/" in window.upload_url(window.upload_registry.all()[0])
    dialog = QRCodeDialog(
        "http://127.0.0.1:9876/share/d/test",
        window.registry.all()[0],
        window.i18n,
        window,
    )
    assert dialog.windowTitle() == "分享二维码"
    window.save_config_now()
    assert config_path().exists()
    saved = load_config()
    assert saved["port"] == 9876 and len(saved["shares"]) == 2
    assert len(saved["uploads"]) == 1 and saved["uploads"][0]["name"] == "界面上传"
    assert saved["font_family"] == "Microsoft YaHei UI"
    assert saved["font_size"] == 13
    assert saved["language"] == "zh"

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    ui_port = probe.getsockname()[1]
    probe.close()
    window.port_input.setValue(ui_port)
    window.base_input.setText("/uishare")
    window.config["firewall_notice_shown"] = True
    window.start_server()
    assert window.is_running()
    _, _, ui_health = fetch(f"http://127.0.0.1:{ui_port}/uishare/health")
    assert json.loads(ui_health)["status"] == "running"
    ui_file_url = window.share_url(window.registry.all()[0])
    _, _, downloaded = fetch(ui_file_url)
    assert downloaded == b"ABCDEFGHIJ"
    window.stop_server()
    assert not window.is_running()

    original_getfqdn = socket.getfqdn

    def forbidden_getfqdn(*_args):
        raise AssertionError("LanHTTPServer must not resolve hostnames during bind")

    socket.getfqdn = forbidden_getfqdn
    try:
        fast_server = LanHTTPServer(
            ("127.0.0.1", 0),
            ShareRequestHandler,
            registry,
            uploads,
            "/share",
            lambda message: None,
        )
        fast_server.server_close()
    finally:
        socket.getfqdn = original_getfqdn

    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
