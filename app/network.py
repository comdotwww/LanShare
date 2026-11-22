"""本机网卡 IPv4 地址枚举。"""
from __future__ import annotations

import ipaddress
import json
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
        # TEST-NET 保留地址：只用于让系统选择出网网卡，不会真正发送数据包。
        for target in ("192.0.2.1", "198.51.100.1", "203.0.113.1"):
            try:
                sock.connect((target, 9))
                ip = sock.getsockname()[0]
                if _valid_ipv4(ip) and not ip.startswith("127."):
                    return ip
            except OSError:
                continue
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


def _linux_entries() -> List[Tuple[str, str]]:
    """在 Linux 上从 `ip -j addr` 提取网卡名与 IPv4。"""
    if sys.platform.startswith("linux") is False:
        return []
    try:
        output = subprocess.run(
            ["ip", "-j", "addr"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        ).stdout
        data = json.loads(output)
        entries: List[Tuple[str, str]] = []
        for interface in data:
            name = str(interface.get("ifname") or "网卡")
            for info in interface.get("addr_info") or []:
                if info.get("family") != "inet":
                    continue
                ip = str(info.get("local") or "")
                if _valid_ipv4(ip) and not ip.startswith(("127.", "169.254.")):
                    entries.append((name, ip))
        return entries
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return []


def _mac_entries() -> List[Tuple[str, str]]:
    """在 macOS 上从 route/ifconfig 提取默认网卡与 IPv4。"""
    if sys.platform != "darwin":
        return []
    interface = ""
    try:
        route_output = subprocess.run(
            ["route", "-n", "get", "default"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        ).stdout
        match = re.search(r"^\s*interface:\s*(\S+)", route_output, re.MULTILINE)
        if match:
            interface = match.group(1)
    except (OSError, subprocess.SubprocessError):
        interface = ""

    commands = [[ "ifconfig", interface ]] if interface else [["ifconfig", "-a"]]
    entries: List[Tuple[str, str]] = []
    for command in commands:
        try:
            output = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for line in output.splitlines():
            match = re.search(r"\binet\s+(?:\d{1,3}\.){3}\d{1,3}", line)
            if not match:
                continue
            ip = match.group(0).rsplit(" ", 1)[-1]
            if _valid_ipv4(ip) and not ip.startswith(("127.", "169.254.")):
                entries.append((interface or "本机 IPv4", ip))
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

    if sys.platform == "win32":
        platform_entries = _ipconfig_entries()
    elif sys.platform == "darwin":
        platform_entries = _mac_entries()
    else:
        platform_entries = _linux_entries()

    for label, ip in platform_entries + _socket_entries():
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
