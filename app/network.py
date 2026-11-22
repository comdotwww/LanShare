"""本机网卡 IPv4 地址枚举。"""
from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
import sys
from typing import List, Tuple

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _valid_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ipaddress.AddressValueError:
        return False


def _default_lan_ip() -> str | None:
    """通过 UDP connect 获取出网网卡地址，不会真正发送数据包。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("223.5.5.5", 80))
        ip = sock.getsockname()[0]
        return ip if _valid_ipv4(ip) and not ip.startswith("127.") else None
    except OSError:
        return None
    finally:
        sock.close()


def _ipconfig_entries() -> List[Tuple[str, str]]:
    """在 Windows 上从 ipconfig 输出中提取网卡名称与 IPv4 地址。"""
    if sys.platform != "win32":
        return []
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        output = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="ignore",
            timeout=5,
            creationflags=flags,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    entries: List[Tuple[str, str]] = []
    adapter = "网卡"
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            adapter = "网卡"
            continue
        if stripped.endswith(":") and "IPv4" not in stripped:
            adapter = stripped[:-1].strip() or "网卡"
            continue
        if "IPv4" in stripped:
            match = IPV4_RE.search(stripped)
            if match:
                ip = match.group(0)
                if _valid_ipv4(ip) and not ip.startswith("169.254."):
                    entries.append((adapter, ip))
    return entries


def _socket_entries() -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        addresses = []
    for ip in addresses:
        if _valid_ipv4(ip) and not ip.startswith("169.254."):
            entries.append(("本机 IPv4", ip))
    return entries


def list_bind_addresses() -> List[Tuple[str, str]]:
    """返回 (显示文本, IP) 列表，第一项为任意地址。"""
    result: List[Tuple[str, str]] = [
        ("所有网卡 · 0.0.0.0", "0.0.0.0"),
    ]
    seen = {"0.0.0.0"}

    default_ip = _default_lan_ip()
    if default_ip and default_ip not in seen:
        result.append((f"主网卡 · {default_ip}", default_ip))
        seen.add(default_ip)

    for label, ip in _ipconfig_entries() + _socket_entries():
        if ip in seen:
            continue
        seen.add(ip)
        result.append((f"{label} · {ip}", ip))

    if "127.0.0.1" not in seen:
        result.append(("本地回环 · 127.0.0.1", "127.0.0.1"))
    return result


def lan_ip() -> str:
    """用于生成访问链接的局域网 IP；绑定 0.0.0.0 时使用。"""
    return _default_lan_ip() or "127.0.0.1"
