"""分享项注册与线程安全访问。"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Share:
    token: str
    path: str
    kind: str
    created_at: float


class ShareRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: Dict[str, Share] = {}
        self._paths: Dict[str, str] = {}

    @staticmethod
    def detect_kind(path: str | Path) -> str:
        p = Path(path)
        return "directory" if p.is_dir() else "file"

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(6)

    def add(self, path: str | Path) -> Share:
        abs_path = str(Path(path).expanduser().resolve())
        with self._lock:
            existing_token = self._paths.get(abs_path)
            if existing_token and existing_token in self._items:
                return self._items[existing_token]
            token = self._new_token()
            while token in self._items:
                token = self._new_token()
            import time

            share = Share(
                token=token,
                path=abs_path,
                kind=self.detect_kind(abs_path),
                created_at=time.time(),
            )
            self._items[token] = share
            self._paths[abs_path] = token
            return share

    def get(self, token: str) -> Share | None:
        with self._lock:
            return self._items.get(token)

    def remove(self, token: str) -> Share | None:
        with self._lock:
            share = self._items.pop(token, None)
            if share:
                self._paths.pop(share.path, None)
            return share

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._paths.clear()

    def all(self) -> List[Share]:
        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.created_at)

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def to_config(self) -> List[Dict[str, Any]]:
        return [asdict(share) for share in self.all()]

    def load_from_config(self, items: List[Dict[str, Any]]) -> None:
        self.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            token = str(item.get("token") or "").strip()
            path = str(item.get("path") or "").strip()
            if not token or not path:
                continue
            try:
                created_at = float(item.get("created_at", 0))
            except (TypeError, ValueError):
                import time

                created_at = time.time()
            kind = str(item.get("kind") or self.detect_kind(path))
            with self._lock:
                if token in self._items or path in self._paths:
                    continue
                share = Share(token=token, path=path, kind=kind, created_at=created_at)
                self._items[token] = share
                self._paths[path] = token


@dataclass
class UploadFolder:
    token: str
    name: str
    path: str
    created_at: float


class UploadRegistry:
    """已授权上传文件夹注册表。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: Dict[str, UploadFolder] = {}
        self._paths: Dict[str, str] = {}

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(6)

    def add(self, name: str, path: str | Path) -> UploadFolder:
        abs_path = str(Path(path).expanduser().resolve())
        clean_name = str(name).strip() or (Path(abs_path).name or "uploads")
        with self._lock:
            existing_token = self._paths.get(abs_path)
            if existing_token and existing_token in self._items:
                return self._items[existing_token]
            token = self._new_token()
            while token in self._items:
                token = self._new_token()
            folder = UploadFolder(
                token=token,
                name=clean_name,
                path=abs_path,
                created_at=time.time(),
            )
            self._items[token] = folder
            self._paths[abs_path] = token
            return folder

    def get(self, token: str) -> UploadFolder | None:
        with self._lock:
            return self._items.get(token)

    def remove(self, token: str) -> UploadFolder | None:
        with self._lock:
            folder = self._items.pop(token, None)
            if folder:
                self._paths.pop(folder.path, None)
            return folder

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._paths.clear()

    def all(self) -> List[UploadFolder]:
        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.created_at)

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def to_config(self) -> List[Dict[str, Any]]:
        return [asdict(folder) for folder in self.all()]

    def load_from_config(self, items: List[Dict[str, Any]]) -> None:
        self.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            token = str(item.get("token") or "").strip()
            path = str(item.get("path") or "").strip()
            if not token or not path:
                continue
            try:
                created_at = float(item.get("created_at", 0))
            except (TypeError, ValueError):
                created_at = time.time()
            name = str(item.get("name") or "").strip() or (Path(path).name or "uploads")
            with self._lock:
                if token in self._items or path in self._paths:
                    continue
                folder = UploadFolder(
                    token=token,
                    name=name,
                    path=path,
                    created_at=created_at,
                )
                self._items[token] = folder
                self._paths[path] = token
