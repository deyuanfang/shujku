"""Local filesystem storage scanner."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.services.storage import (
    BaseStorage, StorageInfo, StorageType, StorageStatus, ScannedFile,
    is_supported_file, infer_content_type,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class LocalStorage(BaseStorage):
    """Scanner for local filesystem directories."""

    def __init__(self):
        self._root: Path | None = None
        self._info: StorageInfo | None = None

    async def connect(self, config: dict) -> bool:
        path = config.get("root_path", "")
        self._root = Path(path).resolve()
        if not self._root.exists():
            self._info = StorageInfo(
                id=config.get("id", str(uuid.uuid4())),
                name=config.get("name", "本地存储"),
                type=StorageType.LOCAL,
                status=StorageStatus.ERROR,
                error_message=f"路径不存在: {path}",
            )
            return False
        self._info = None
        return True

    async def disconnect(self) -> None:
        self._root = None

    async def scan(
        self,
        root_path: str = "",
        recursive: bool = True,
        file_types: list[str] | None = None,
        progress_callback=None,
    ) -> list[ScannedFile]:
        if not self._root:
            return []

        scan_root = self._root / root_path if root_path else self._root
        if not scan_root.exists():
            return []

        files = []
        all_files = []

        # Collect all files first for progress tracking
        if recursive:
            for dirpath, _, filenames in os.walk(scan_root):
                for fname in filenames:
                    all_files.append(Path(dirpath) / fname)
        else:
            all_files = [p for p in scan_root.iterdir() if p.is_file()]

        total = len(all_files)
        for i, filepath in enumerate(all_files):
            if not is_supported_file(filepath.name):
                continue
            if file_types:
                ext = filepath.suffix.lower()
                if ext not in file_types and f".{ext.lstrip('.')}" not in file_types:
                    continue

            stat = filepath.stat()
            rel_path = str(filepath.relative_to(self._root))

            files.append(ScannedFile(
                path=rel_path,
                name=filepath.name,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                content_type=infer_content_type(filepath.name),
            ))

            if progress_callback:
                await progress_callback(i + 1, total)

        return files

    async def read_file(self, file_path: str) -> bytes:
        if not self._root:
            raise RuntimeError("Storage not connected")
        full_path = (self._root / file_path).resolve()
        if not str(full_path).startswith(str(self._root)):
            raise ValueError("Path traversal detected")
        return full_path.read_bytes()

    async def write_file(self, file_path: str, content: bytes) -> bool:
        if not self._root:
            return False
        full_path = (self._root / file_path).resolve()
        if not str(full_path).startswith(str(self._root)):
            return False
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return True

    async def delete_file(self, file_path: str) -> bool:
        if not self._root:
            return False
        full_path = (self._root / file_path).resolve()
        if not str(full_path).startswith(str(self._root)):
            return False
        if full_path.exists():
            full_path.unlink()
        return True

    async def get_info(self) -> StorageInfo:
        if self._info:
            return self._info
        if not self._root:
            return StorageInfo(id="", name="", type=StorageType.LOCAL, status=StorageStatus.OFFLINE)

        try:
            usage = os.statvfs(str(self._root)) if hasattr(os, 'statvfs') else None
            if usage:
                total = usage.f_frsize * usage.f_blocks
                free = usage.f_frsize * usage.f_bavail
                used = total - free
                return StorageInfo(
                    id="local",
                    name=self._root.name or "本地存储",
                    type=StorageType.LOCAL,
                    status=StorageStatus.ONLINE,
                    root_path=str(self._root),
                    total_size_gb=round(total / (1024**3), 1),
                    used_size_gb=round(used / (1024**3), 1),
                    free_size_gb=round(free / (1024**3), 1),
                )
        except Exception:
            pass

        return StorageInfo(
            id="local",
            name=self._root.name or "本地存储",
            type=StorageType.LOCAL,
            status=StorageStatus.ONLINE,
            root_path=str(self._root),
        )

    async def is_available(self) -> bool:
        return self._root is not None and self._root.exists()
