"""Removable / mobile storage scanner (USB drives, SD cards, external HDDs)."""

import os
import uuid
import subprocess
import platform
from pathlib import Path
from typing import Optional

from app.services.storage import (
    BaseStorage, StorageInfo, StorageType, StorageStatus, ScannedFile,
    is_supported_file, infer_content_type,
)
from app.services.storage.local import LocalStorage


class RemovableStorage(BaseStorage):
    """Scanner for removable storage devices (USB drives, SD cards, external HDDs).

    Auto-detects removable drives on all major platforms.
    """

    def __init__(self):
        self._delegate: LocalStorage | None = None
        self._info: StorageInfo | None = None

    async def connect(self, config: dict) -> bool:
        path = config.get("root_path", "")
        name = config.get("name", "移动存储")

        if path:
            root = Path(path)
            if root.exists():
                self._delegate = LocalStorage()
                ok = await self._delegate.connect({"root_path": str(root), "name": name})
                self._info = StorageInfo(
                    id=config.get("id", str(uuid.uuid4())),
                    name=name,
                    type=StorageType.REMOVABLE,
                    status=StorageStatus.ONLINE if ok else StorageStatus.ERROR,
                    root_path=str(root),
                )
                return ok

        # Auto-detect removable drives
        drives = await self._detect_removable_drives()
        if not drives:
            self._info = StorageInfo(
                id=config.get("id", str(uuid.uuid4())),
                name=name,
                type=StorageType.REMOVABLE,
                status=StorageStatus.OFFLINE,
                error_message="未发现可移动存储设备",
            )
            return False

        selected = drives[0]
        for drive in drives:
            if name in drive.get("label", "") or name in drive.get("name", ""):
                selected = drive
                break

        self._delegate = LocalStorage()
        ok = await self._delegate.connect({"root_path": selected["path"], "name": selected["name"]})
        self._info = StorageInfo(
            id=config.get("id", str(uuid.uuid4())),
            name=selected["name"],
            type=StorageType.REMOVABLE,
            status=StorageStatus.ONLINE if ok else StorageStatus.ERROR,
            root_path=selected["path"],
            config={"label": selected.get("label", ""), "serial": selected.get("serial", "")},
        )
        return ok

    async def _detect_removable_drives(self) -> list[dict]:
        """Detect removable drives on the system."""
        drives = []
        system = platform.system()

        if system == "Windows":
            try:
                import win32api
                drives_list = win32api.GetLogicalDriveStrings()
                drives_list = drives_list.split('\x00')
                for drive in drives_list:
                    if drive and os.path.exists(drive):
                        drive_type = win32api.GetDriveType(drive)
                        if drive_type == 2:  # DRIVE_REMOVABLE
                            label = ""
                            try:
                                import win32file
                                volume_info = win32file.GetVolumeInformation(drive)
                                label = volume_info[0]
                            except Exception:
                                pass
                            drives.append({
                                "name": f"{label} ({drive})" if label else f"可移动磁盘 ({drive})",
                                "path": drive,
                                "label": label,
                            })
            except ImportError:
                # Fallback: check common removable drive letters
                for letter in "DEFGHIJKLMNO":
                    drive_path = f"{letter}:\\"
                    if os.path.exists(drive_path):
                        drives.append({
                            "name": f"可移动磁盘 ({letter}:)",
                            "path": drive_path,
                        })

        elif system == "Linux":
            # Check /media for auto-mounted removable drives
            media_dir = "/media"
            if os.path.exists(media_dir):
                import pwd
                username = os.getenv("USER") or pwd.getpwuid(os.getuid()).pw_name
                user_media = os.path.join(media_dir, username)
                search_paths = [media_dir, user_media, "/mnt"]
                for search in search_paths:
                    if os.path.exists(search):
                        for entry in os.listdir(search):
                            full_path = os.path.join(search, entry)
                            if os.path.isdir(full_path) and os.path.ismount(full_path) if hasattr(os, 'ismount') else True:
                                # Check if it's not the root device
                                try:
                                    result = subprocess.run(
                                        ["findmnt", "-n", "-o", "FSTYPE", full_path],
                                        capture_output=True, text=True, timeout=3
                                    )
                                    fstype = result.stdout.strip()
                                    if fstype in ("vfat", "exfat", "ntfs", "ext4", "ext3", "hfsplus"):
                                        drives.append({
                                            "name": f"移动存储 ({entry})",
                                            "path": full_path,
                                            "label": entry,
                                        })
                                except Exception:
                                    pass

        elif system == "Darwin":
            # Check /Volumes for external drives
            volumes = "/Volumes"
            if os.path.exists(volumes):
                for entry in os.listdir(volumes):
                    full_path = os.path.join(volumes, entry)
                    if entry not in ("Macintosh HD", "Recovery", "Preboot") and os.path.isdir(full_path):
                        drives.append({
                            "name": f"移动存储 ({entry})",
                            "path": full_path,
                            "label": entry,
                        })

        return drives

    async def disconnect(self) -> None:
        if self._delegate:
            await self._delegate.disconnect()

    async def scan(self, root_path: str = "", recursive: bool = True,
                   file_types: list[str] | None = None, progress_callback=None) -> list[ScannedFile]:
        if self._delegate:
            return await self._delegate.scan(root_path, recursive, file_types, progress_callback)
        return []

    async def read_file(self, file_path: str) -> bytes:
        if self._delegate:
            return await self._delegate.read_file(file_path)
        raise RuntimeError("Removable storage not connected")

    async def write_file(self, file_path: str, content: bytes) -> bool:
        if self._delegate:
            return await self._delegate.write_file(file_path, content)
        return False

    async def delete_file(self, file_path: str) -> bool:
        if self._delegate:
            return await self._delegate.delete_file(file_path)
        return False

    async def get_info(self) -> StorageInfo:
        if self._info:
            return self._info
        if self._delegate:
            info = await self._delegate.get_info()
            info.type = StorageType.REMOVABLE
            return info
        return StorageInfo(id="removable", name="移动存储", type=StorageType.REMOVABLE, status=StorageStatus.OFFLINE)

    async def is_available(self) -> bool:
        return self._delegate is not None and await self._delegate.is_available()
