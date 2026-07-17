"""NAS / Network share storage scanner (SMB/CIFS, NFS detection)."""

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


class NASStorage(BaseStorage):
    """Scanner for NAS / network shares.

    On Windows: detects mapped network drives (Z:, Y:, etc.) and UNC paths.
    On Linux/Mac: detects mounted NFS/CIFS shares under /mnt, /media, /Volumes.
    """

    def __init__(self):
        self._delegate: LocalStorage | None = None
        self._info: StorageInfo | None = None

    async def connect(self, config: dict) -> bool:
        path = config.get("root_path", "")
        name = config.get("name", "NAS存储")
        share_type = config.get("share_type", "auto")  # smb, nfs, auto

        # If a specific path is given, try to use it directly
        if path:
            root = Path(path)
            if root.exists():
                self._delegate = LocalStorage()
                ok = await self._delegate.connect({"root_path": str(root), "name": name})
                self._info = StorageInfo(
                    id=config.get("id", str(uuid.uuid4())),
                    name=name,
                    type=StorageType.NAS,
                    status=StorageStatus.ONLINE if ok else StorageStatus.ERROR,
                    root_path=str(root),
                )
                return ok

        # Auto-detect network shares
        shares = await self._detect_network_shares()
        if not shares:
            self._info = StorageInfo(
                id=config.get("id", str(uuid.uuid4())),
                name=name,
                type=StorageType.NAS,
                status=StorageStatus.OFFLINE,
                error_message="未发现可用的网络共享",
            )
            return False

        # Use the first available share or match by name
        selected = shares[0]
        for share in shares:
            if name in share["name"] or name in share["path"]:
                selected = share
                break

        self._delegate = LocalStorage()
        ok = await self._delegate.connect({"root_path": selected["path"], "name": selected["name"]})
        self._info = StorageInfo(
            id=config.get("id", str(uuid.uuid4())),
            name=selected["name"],
            type=StorageType.NAS,
            status=StorageStatus.ONLINE if ok else StorageStatus.ERROR,
            root_path=selected["path"],
            config={"share_type": selected.get("type", "unknown")},
        )
        return ok

    async def _detect_network_shares(self) -> list[dict]:
        """Detect available network shares on the system."""
        shares = []
        system = platform.system()

        if system == "Windows":
            # Check mapped network drives
            try:
                result = subprocess.run(
                    ["net", "use"], capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.split("\n"):
                    # Parse lines like "OK           Z:        \\server\share"
                    parts = line.strip().split()
                    if len(parts) >= 3 and ":" in parts[1]:
                        drive_letter = parts[1]
                        unc_path = parts[2] if len(parts) > 2 else ""
                        drive_path = drive_letter + "\\"
                        if os.path.exists(drive_path):
                            shares.append({
                                "name": f"网络驱动器 ({drive_letter})",
                                "path": drive_path,
                                "type": "smb",
                                "unc": unc_path,
                            })
            except Exception:
                pass

            # Also check common NAS UNC paths
            # Try to access common NAS hostnames
            for nas_host in ["nas", "diskstation", "synology", "qnap", "truenas"]:
                unc = f"\\\\{nas_host}"
                try:
                    result = subprocess.run(
                        ["net", "view", unc], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        shares.append({
                            "name": f"NAS ({nas_host})",
                            "path": unc,
                            "type": "smb",
                        })
                except Exception:
                    pass

        elif system in ("Linux", "Darwin"):
            # Check /mnt and /media for NFS/CIFS mounts
            search_dirs = ["/mnt", "/media", "/Volumes"]
            for search_dir in search_dirs:
                if os.path.exists(search_dir):
                    for entry in os.listdir(search_dir):
                        full_path = os.path.join(search_dir, entry)
                        if os.path.ismount(full_path) if hasattr(os.path, 'ismount') else os.path.isdir(full_path):
                            # Check if it's a network filesystem
                            try:
                                result = subprocess.run(
                                    ["df", "-T", full_path] if system == "Linux" else ["mount"],
                                    capture_output=True, text=True, timeout=5
                                )
                                output = result.stdout.lower()
                                if any(fs in output for fs in ["nfs", "cifs", "smb", "afp", "fuse"]):
                                    shares.append({
                                        "name": f"网络共享 ({entry})",
                                        "path": full_path,
                                        "type": "nfs" if "nfs" in output else "smb",
                                    })
                            except Exception:
                                pass

        return shares

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
        raise RuntimeError("NAS storage not connected")

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
            info.type = StorageType.NAS
            return info
        return StorageInfo(id="nas", name="NAS存储", type=StorageType.NAS, status=StorageStatus.OFFLINE)

    async def is_available(self) -> bool:
        return self._delegate is not None and await self._delegate.is_available()
