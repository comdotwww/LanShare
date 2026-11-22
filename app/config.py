"""配置读写与基础路径规范化。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

APP_NAME = "LanFileShare"

DEFAULT_CONFIG: Dict[str, Any] = {
    "bind_ip": "0.0.0.0",
    "port": 8765,
    "base_path": "/share",
    "shares": [],
    "uploads": [],
    "font_family": "Microsoft YaHei UI",
    "font_size": 13,
    "language": "zh",
    "firewall_notice_shown": False,
}


def config_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    path = Path(appdata) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def normalize_base_path(value: str) -> str:
    """把用户输入整理成以 / 开头、无尾斜杠的请求路径；根路径返回 /。"""
    raw = (value or "").strip()
    if not raw:
        return "/"
    if not raw.startswith("/"):
        raw = "/" + raw
    raw = re.sub(r"/{2,}", "/", raw)
    raw = raw.rstrip("/")
    return raw or "/"


def join_url_path(base_path: str, suffix: str) -> str:
    base = normalize_base_path(base_path)
    prefix = "" if base == "/" else base
    return f"{prefix}/{suffix.lstrip('/')}" if suffix else (prefix or "/")


def load_config() -> Dict[str, Any]:
    path = config_path()
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return dict(DEFAULT_CONFIG)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)

    result = dict(DEFAULT_CONFIG)
    result.update(data)
    result["bind_ip"] = str(result.get("bind_ip") or "0.0.0.0")
    try:
        result["port"] = int(result.get("port") or DEFAULT_CONFIG["port"])
    except (TypeError, ValueError):
        result["port"] = DEFAULT_CONFIG["port"]
    result["base_path"] = normalize_base_path(str(result.get("base_path") or "/share"))
    shares = result.get("shares")
    result["shares"] = shares if isinstance(shares, list) else []
    uploads = result.get("uploads")
    result["uploads"] = uploads if isinstance(uploads, list) else []
    result["font_family"] = str(result.get("font_family") or DEFAULT_CONFIG["font_family"])
    try:
        font_size = int(result.get("font_size") or DEFAULT_CONFIG["font_size"])
    except (TypeError, ValueError):
        font_size = DEFAULT_CONFIG["font_size"]
    result["font_size"] = max(9, min(22, font_size))
    language = str(result.get("language") or "zh").lower()
    result["language"] = "en" if language.startswith("en") else "zh"
    result["firewall_notice_shown"] = bool(result.get("firewall_notice_shown", False))
    return result


def save_config(config: Dict[str, Any]) -> None:
    path = config_path()
    data = {
        "bind_ip": config.get("bind_ip", "0.0.0.0"),
        "port": int(config.get("port", DEFAULT_CONFIG["port"])),
        "base_path": normalize_base_path(str(config.get("base_path", "/share"))),
        "shares": config.get("shares", []),
        "uploads": config.get("uploads", []),
        "font_family": str(config.get("font_family") or DEFAULT_CONFIG["font_family"]),
        "font_size": max(9, min(22, int(config.get("font_size") or DEFAULT_CONFIG["font_size"]))),
        "language": "en" if str(config.get("language", "zh")).lower().startswith("en") else "zh",
        "firewall_notice_shown": bool(config.get("firewall_notice_shown", False)),
    }
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
