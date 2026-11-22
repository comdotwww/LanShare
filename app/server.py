"""局域网 HTTP 文件分享服务。"""
from __future__ import annotations

import html
import mimetypes
import os
import re
import socket
from datetime import datetime
from email.parser import BytesParser
from email import policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Tuple
from urllib.parse import quote, unquote, urlsplit

from .config import normalize_base_path
from .i18n import web_text
from .registry import Share, ShareRegistry, UploadFolder, UploadRegistry

CHUNK_SIZE = 64 * 1024
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class LanHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 16

    def __init__(
        self,
        server_address: Tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        registry: ShareRegistry,
        upload_registry: UploadRegistry,
        base_path: str,
        log_callback: Callable[[str], None] | None = None,
        language: str = "zh",
    ) -> None:
        self.registry = registry
        self.upload_registry = upload_registry
        self.base_path = normalize_base_path(base_path)
        self.log_callback = log_callback
        self.language = language
        self.request_count = 0
        super().__init__(server_address, handler_class)

    def server_bind(self) -> None:
        """跳过 HTTPServer 的反向 DNS 解析，避免启动时阻塞数秒。"""
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port


class ShareRequestHandler(BaseHTTPRequestHandler):
    server_version = "LanFileShare/1.0"
    sys_version = ""

    def log_message(self, fmt: str, *args: object) -> None:
        # 日志统一交给界面展示，避免污染控制台。
        return

    def send_response(self, code: int, message: str | None = None) -> None:
        self._status_code = code
        super().send_response(code, message)

    def do_GET(self) -> None:
        self._handle_request(head_only=False)

    def do_HEAD(self) -> None:
        self._handle_request(head_only=True)

    def do_POST(self) -> None:
        self._handle_post()

    def _log(self, message: str) -> None:
        callback = getattr(self.server, "log_callback", None)
        if callback:
            callback(message)

    def _handle_request(self, head_only: bool) -> None:
        self._status_code = 500
        server: LanHTTPServer = self.server  # type: ignore[assignment]
        server.request_count += 1
        target = urlsplit(self.path).path
        web = web_text(server.language)
        try:
            decoded = unquote(target)
            base = server.base_path
            prefix = "" if base == "/" else base
            if prefix and decoded != prefix and not decoded.startswith(prefix + "/"):
                self._send_text(404, web["path_mismatch"])
                return

            rel = decoded[len(prefix):].strip("/") if prefix else decoded.strip("/")
            if not rel:
                self._send_html(200, self._landing_page())
                return
            if rel == "health":
                self._send_json(
                    200,
                    {"status": "running", "shares": server.registry.count(), "uploads": server.upload_registry.count()},
                )
                return

            parts = rel.split("/")
            if parts[0] == "d" and len(parts) >= 2:
                self._serve_file_share(parts[1], head_only)
                return
            if parts[0] == "s" and len(parts) >= 2:
                self._serve_directory_share(parts[1], parts[2:], head_only)
                return
            if parts[0] == "u" and len(parts) >= 2:
                self._serve_upload_page(parts[1])
                return
            self._send_text(404, web["invalid_link"])
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # 避免单个请求导致服务线程报错退出
            try:
                self._send_text(
                    500,
                    web["server_error"].format(error=html.escape(str(exc))),
                )
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            client = self.client_address[0] if self.client_address else "-"
            self._log(f"{client} {self.command} {target} → {getattr(self, '_status_code', 500)}")

    def _handle_post(self) -> None:
        self._status_code = 500
        server: LanHTTPServer = self.server  # type: ignore[assignment]
        server.request_count += 1
        target = urlsplit(self.path).path
        web = web_text(server.language)
        try:
            decoded = unquote(target)
            base = server.base_path
            prefix = "" if base == "/" else base
            if prefix and decoded != prefix and not decoded.startswith(prefix + "/"):
                self._send_text(404, web["path_mismatch"])
                return
            rel = decoded[len(prefix):].strip("/") if prefix else decoded.strip("/")
            parts = rel.split("/")
            if parts[0] == "u" and len(parts) >= 2:
                self._handle_upload(parts[1])
                return
            self._send_text(404, web["invalid_link"])
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            try:
                self._send_text(
                    500,
                    web["server_error"].format(error=html.escape(str(exc))),
                )
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            client = self.client_address[0] if self.client_address else "-"
            self._log(f"{client} {self.command} {target} → {getattr(self, '_status_code', 500)}")

    @staticmethod
    def _safe_filename(filename: str) -> str | None:
        name = str(filename or "").replace("\\", "/").strip()
        name = name.rsplit("/", 1)[-1].strip().strip('"')
        name = "".join(char for char in name if ord(char) >= 32 and char not in '<>:|?*')
        name = name.strip(" .")
        if not name or name in {".", ".."}:
            return None
        return name[:180]

    def _handle_upload(self, token: str) -> None:
        web = web_text(self.server.language)  # type: ignore[attr-defined]
        folder: UploadFolder | None = self.server.upload_registry.get(token)  # type: ignore[assignment]
        if not folder:
            self._send_text(404, web["upload_forbidden"])
            return
        root = Path(folder.path).resolve()
        if not root.is_dir():
            self._send_text(404, web["upload_folder_missing"])
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            self._send_text(400, web["upload_method"])
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            self._send_text(400, web["upload_invalid_form"])
            return
        if length > MAX_UPLOAD_BYTES:
            self._send_text(413, web["upload_too_large"])
            return

        body = self.rfile.read(length)
        try:
            raw = (
                b"Content-Type: " + content_type.encode("latin-1", "replace")
                + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
            )
            message = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception as exc:
            self._send_text(
                400,
                web["upload_failed"].format(error=html.escape(str(exc))),
            )
            return
        if not message.is_multipart():
            self._send_text(400, web["upload_invalid_form"])
            return

        uploaded = 0
        errors: List[str] = []
        for part in message.iter_parts():
            raw_name = part.get_filename()
            if not raw_name:
                continue
            safe_name = self._safe_filename(raw_name)
            if not safe_name:
                errors.append(web["upload_no_filename"])
                continue
            destination = (root / safe_name).resolve()
            if destination.parent != root:
                errors.append(web["upload_no_filename"])
                continue
            payload = part.get_payload(decode=True) or b""
            try:
                with destination.open("wb") as output:
                    output.write(payload)
                uploaded += 1
            except OSError as exc:
                errors.append(html.escape(str(exc)))

        if uploaded == 0 and not errors:
            self._send_text(400, web["no_file_selected"])
            return
        message_text = web["upload_success"].format(count=uploaded) if uploaded else ""
        back_url = urlsplit(self.path).path
        status = 200 if uploaded else 400
        self._send_html(
            status,
            self._upload_result_page(web, folder.name, back_url, message_text, errors),
        )
        callback = getattr(self.server, "log_callback", None)
        if callback:
            callback(f"UPLOAD {folder.name} ← {uploaded}")

    def _serve_upload_page(self, token: str) -> None:
        web = web_text(self.server.language)  # type: ignore[attr-defined]
        folder: UploadFolder | None = self.server.upload_registry.get(token)  # type: ignore[assignment]
        if not folder:
            self._send_text(404, web["upload_forbidden"])
            return
        root = Path(folder.path).resolve()
        if not root.is_dir():
            self._send_text(404, web["upload_folder_missing"])
            return
        try:
            files = sorted(
                (entry for entry in root.iterdir() if entry.is_file()),
                key=lambda item: item.name.lower(),
            )
        except OSError:
            files = []
        rows = "".join(
            f"<li><span>{html.escape(item.name)}</span><small>{format_size(item.stat().st_size) if item.exists() else ''}</small></li>"
            for item in files
        )
        file_list = (
            f'<ul class="files">{rows}</ul>' if rows else f'<p class="empty">{html.escape(web["no_files"])}</p>'
        )
        title = html.escape(web["upload_page_title"].format(name=folder.name))
        lang = "zh-CN" if self.server.language == "zh" else "en"  # type: ignore[attr-defined]
        self._send_html(200, f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{color-scheme:light}}*{{box-sizing:border-box}}
body{{margin:0;padding:32px 16px;background:#f5f7fb;color:#111827;font-family:system-ui,sans-serif}}
.wrap{{max-width:760px;margin:0 auto}}
.panel{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;box-shadow:0 8px 24px rgba(15,23,42,.06);overflow:hidden}}
.head{{padding:24px 28px;border-bottom:1px solid #eef0f4}}
h1{{margin:0 0 8px;font-size:22px;word-break:break-all}}
p{{margin:0;color:#6b7280;font-size:13px}}
.form{{padding:24px 28px}}
input[type=file]{{width:100%;padding:12px;border:1px dashed #93c5fd;border-radius:10px;background:#f8fbff}}
button{{margin-top:16px;padding:10px 20px;border:0;border-radius:8px;background:#2563eb;color:#fff;font-size:14px;font-weight:600;cursor:pointer}}
button:hover{{background:#1d4ed8}}
.section{{padding:0 28px 24px}}
h2{{font-size:15px;margin:0 0 12px}}
.files{{list-style:none;margin:0;padding:0}}
.files li{{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;border:1px solid #eef0f4;border-radius:8px;margin-bottom:8px;font-size:14px;word-break:break-all}}
.files small{{color:#9ca3af;white-space:nowrap}}
.empty{{padding:24px;text-align:center;color:#9ca3af}}
.foot{{padding:12px 28px;background:#fafbfc;color:#9ca3af;text-align:center;font-size:12px}}
</style></head><body><div class="wrap"><div class="panel">
<div class="head"><h1>{title}</h1><p>{html.escape(web["upload_intro"])} {html.escape(web["upload_size_hint"])}</p></div>
<div class="form"><form method="post" enctype="multipart/form-data">
<input type="file" name="files" multiple>
<button type="submit">{html.escape(web["upload_button"])}</button>
</form></div>
<div class="section"><h2>{html.escape(web["existing_files"])}</h2>{file_list}</div>
<div class="foot">{html.escape(web["footer"])}</div>
</div></div></body></html>""")

    def _upload_result_page(
        self,
        web: Dict[str, str],
        folder_name: str,
        back_url: str,
        message: str,
        errors: List[str],
    ) -> str:
        title = html.escape(web["upload_page_title"].format(name=folder_name))
        messages = ""
        if message:
            messages += f'<div class="ok">{html.escape(message)}</div>'
        for error in errors:
            messages += f'<div class="error">{html.escape(error)}</div>'
        return f"""<!doctype html><html lang="{'zh-CN' if self.server.language == 'zh' else 'en'}"><head><meta charset="utf-8">
<title>{title}</title><style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f5f7fb;color:#111827;font-family:system-ui,sans-serif}}.box{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:32px 40px;text-align:center;min-width:320px}}h1{{font-size:20px;margin:0 0 16px}}.ok{{color:#15803d;margin:8px 0}}.error{{color:#b91c1c;margin:8px 0;font-size:13px}}a{{display:inline-block;margin-top:16px;color:#2563eb}}</style></head>
<body><div class="box"><h1>{title}</h1>{messages}<a href="{html.escape(back_url, quote=True)}">{html.escape(web["upload_refresh"])}</a></div></body></html>"""

    def _serve_file_share(self, token: str, head_only: bool) -> None:
        web = web_text(self.server.language)  # type: ignore[attr-defined]
        share: Share | None = self.server.registry.get(token)  # type: ignore[assignment]
        if not share:
            self._send_text(404, web["invalid_link"])
            return
        path = Path(share.path)
        if not path.is_file():
            self._send_text(404, web["missing_file"])
            return
        self._send_file(path, head_only)

    def _serve_directory_share(self, token: str, sub_parts: List[str], head_only: bool) -> None:
        web = web_text(self.server.language)  # type: ignore[attr-defined]
        share: Share | None = self.server.registry.get(token)  # type: ignore[assignment]
        if not share:
            self._send_text(404, web["invalid_link"])
            return
        root = Path(share.path).resolve()
        if not root.is_dir():
            self._send_text(404, web["missing_dir"])
            return

        try:
            target = root.joinpath(*sub_parts).resolve()
        except (OSError, RuntimeError):
            self._send_text(400, web["invalid_request"])
            return
        if target != root and root not in target.parents:
            self._send_text(403, web["forbidden"])
            return
        if not target.exists():
            self._send_text(404, web["not_found"])
            return
        if target.is_file():
            self._send_file(target, head_only)
            return
        if target.is_dir():
            self._send_html(200, self._directory_page(share, root, target, sub_parts))
            return
        self._send_text(404, web["unsupported"])

    def _directory_page(self, share: Share, root: Path, current: Path, parts: List[str]) -> str:
        web = web_text(self.server.language)  # type: ignore[attr-defined]
        base = self.server.base_path  # type: ignore[assignment]
        prefix = "" if base == "/" else base
        share_url = f"{prefix}/s/{quote(share.token, safe='')}"
        display_parts = [root.name or web["root_label"]] + parts
        links = [f'<a href="{html.escape(share_url, quote=True)}">{html.escape(display_parts[0])}</a>']
        for index, part in enumerate(parts):
            href = share_url + "/" + "/".join(quote(p, safe="") for p in parts[: index + 1]) + "/"
            links.append(f'<a href="{html.escape(href, quote=True)}">{html.escape(part)}</a>')

        try:
            children = sorted(current.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        except OSError:
            children = []

        rows: List[str] = []
        for child in children:
            is_dir = child.is_dir()
            encoded = quote(child.name, safe="")
            href = share_url + "/" + "/".join(quote(p, safe="") for p in parts + [child.name])
            if is_dir:
                href += "/"
            try:
                stat = child.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                size = "—" if is_dir else format_size(stat.st_size)
            except OSError:
                modified, size = "—", "—"
            icon_class = "dir" if is_dir else "file"
            icon_text = web["dir"] if is_dir else web["file"]
            action_text = web["enter"] if is_dir else web["download"]
            rows.append(
                f"""
                <tr>
                  <td>
                    <a class="name-link" href="{html.escape(href, quote=True)}">
                      <span class="icon {icon_class}">{icon_text}</span>
                      <span class="name">{html.escape(child.name)}</span>
                    </a>
                  </td>
                  <td class="cell-size">{size}</td>
                  <td class="cell-time">{modified}</td>
                  <td class="cell-action"><a class="action" href="{html.escape(href, quote=True)}">{html.escape(action_text)}</a></td>
                </tr>"""
            )

        empty = "" if rows else f'<div class="empty">{html.escape(web["empty"])}</div>'
        table = "" if not rows else f"""
            <table>
              <thead><tr><th>{html.escape(web['name'])}</th><th>{html.escape(web['size'])}</th><th>{html.escape(web['modified'])}</th><th>{html.escape(web['action'])}</th></tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>"""
        page_title = web["page_title"].format(name=current.name)
        return f"""<!doctype html>
<html lang="{ 'zh-CN' if self.server.language == 'zh' else 'en' }">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title)}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 32px 16px; background: #f5f7fb; color: #111827; font-family: "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif; }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  .panel {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 16px; box-shadow: 0 8px 24px rgba(15, 23, 42, .06); overflow: hidden; }}
  .head {{ padding: 24px 28px; border-bottom: 1px solid #eef0f4; }}
  h1 {{ margin: 0 0 8px; font-size: 22px; word-break: break-all; }}
  .crumb {{ font-size: 13px; color: #6b7280; word-break: break-all; }}
  .crumb a {{ color: #2563eb; text-decoration: none; }}
  .crumb a:hover {{ text-decoration: underline; }}
  .crumb span {{ margin: 0 6px; color: #9ca3af; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 12px 28px; font-size: 12px; color: #6b7280; font-weight: 600; background: #fafbfc; border-bottom: 1px solid #eef0f4; }}
  td {{ padding: 13px 28px; border-bottom: 1px solid #f3f4f6; font-size: 14px; }}
  tr:last-child td {{ border-bottom: 0; }}
  tr:hover td {{ background: #f9fbff; }}
  .name-link {{ display: inline-flex; align-items: center; gap: 12px; color: #111827; text-decoration: none; }}
  .name-link:hover .name {{ color: #2563eb; }}
  .icon {{ flex: none; width: 52px; height: 26px; border-radius: 7px; font-size: 11px; line-height: 26px; text-align: center; }}
  .icon.dir {{ background: #dbeafe; color: #1d4ed8; }}
  .icon.file {{ background: #f3f4f6; color: #4b5563; }}
  .cell-size, .cell-time {{ color: #6b7280; white-space: nowrap; }}
  .cell-action {{ text-align: right; }}
  .action {{ display: inline-block; padding: 5px 12px; border-radius: 7px; background: #eff6ff; color: #2563eb; text-decoration: none; font-size: 12px; }}
  .action:hover {{ background: #dbeafe; }}
  .empty {{ padding: 56px 28px; text-align: center; color: #9ca3af; }}
  .foot {{ padding: 14px 28px; text-align: center; color: #9ca3af; font-size: 12px; background: #fafbfc; }}
  @media (max-width: 640px) {{
    body {{ padding: 12px 8px; }}
    .head, th, td {{ padding-left: 14px; padding-right: 14px; }}
    .cell-time {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="head">
        <h1>{html.escape(current.name)}</h1>
        <div class="crumb">{"<span>›</span>".join(links)}</div>
      </div>
      {table}{empty}
      <div class="foot">{html.escape(web['footer'])}</div>
    </div>
  </div>
</body>
</html>"""

    def _landing_page(self) -> str:
        web = web_text(self.server.language)  # type: ignore[attr-defined]
        lang = "zh-CN" if self.server.language == "zh" else "en"
        title = html.escape(web["footer"])
        heading = html.escape(web["landing_title"])
        description = html.escape(web["landing_desc"])
        return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f5f7fb;color:#111827;font-family:system-ui,sans-serif}}.box{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:36px 44px;text-align:center;box-shadow:0 8px 24px rgba(15,23,42,.06)}}h1{{font-size:22px;margin:0 0 10px}}p{{color:#6b7280;margin:0;font-size:14px}}</style></head>
<body><div class="box"><h1>{heading}</h1><p>{description}</p></div></body></html>"""

    def _send_file(self, path: Path, head_only: bool) -> None:
        try:
            stat = path.stat()
        except OSError:
            self._send_text(404, web_text(self.server.language)["file_inaccessible"])  # type: ignore[attr-defined]
            return
        size = stat.st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/"):
            content_type += "; charset=utf-8"

        filename = path.name
        ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download"
        ascii_name = ascii_name.replace('"', "'")
        disposition = (
            f'attachment; filename="{ascii_name}"; '
            f"filename*=UTF-8''{quote(filename, safe='')}"
        )

        extra: Dict[str, str] = {
            "Content-Disposition": disposition,
            "Accept-Ranges": "bytes",
            "Last-Modified": self.date_time_string(stat.st_mtime),
        }

        start, end = 0, size - 1
        status = 200
        range_header = self.headers.get("Range")
        if range_header:
            match = RANGE_RE.match(range_header.strip())
            if match:
                start_text, end_text = match.group(1), match.group(2)
                if start_text:
                    start = int(start_text)
                    end = int(end_text) if end_text else size - 1
                elif end_text:
                    suffix = int(end_text)
                    start = max(0, size - suffix)
                    end = size - 1
                else:
                    start, end = 0, -1
                if size == 0 or start >= size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"

        length = max(0, end - start + 1)
        try:
            file_obj = path.open("rb")
        except OSError:
            self._send_text(500, web_text(self.server.language)["file_busy"])  # type: ignore[attr-defined]
            return

        with file_obj:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            for key, value in extra.items():
                self.send_header(key, value)
            self.end_headers()
            if head_only:
                return
            file_obj.seek(start)
            remaining = length
            while remaining > 0:
                chunk = file_obj.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _send_text(self, status: int, text: str) -> None:
        self._send_bytes(status, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _send_html(self, status: int, text: str) -> None:
        self._send_bytes(status, text.encode("utf-8"), "text/html; charset=utf-8")

    def _send_json(self, status: int, payload: Dict[str, object]) -> None:
        import json

        self._send_bytes(
            status,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
