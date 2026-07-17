"""Cloud connector factory and Baidu Cloud implementation."""

from abc import abstractmethod
import hashlib
import json
import time
import urllib.parse
from typing import Optional

import httpx

from app.services.storage import (
    BaseCloudStorage, ScannedFile, StorageInfo, StorageType, StorageStatus,
    is_supported_file, infer_content_type,
)


# ============================================================
# Cloud Connector Base
# ============================================================

class CloudConnector(BaseCloudStorage):
    """Base class with common cloud storage patterns."""

    def __init__(self):
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._config: dict = {}

    @abstractmethod
    async def get_auth_url(self) -> str:
        """Get the OAuth authorization URL."""
        ...

    @abstractmethod
    async def handle_callback(self, code: str) -> bool:
        """Handle OAuth callback with authorization code."""
        ...

    def _ensure_auth(self) -> None:
        if not self._access_token:
            raise RuntimeError("Cloud storage not authenticated. Call authorize() first.")


# ============================================================
# Factory
# ============================================================

def create_cloud_connector(storage_type: StorageType, config: dict | None = None) -> CloudConnector | None:
    config = config or {}
    if storage_type == StorageType.CLOUD_BAIDU:
        return BaiduCloudConnector(
            app_key=config.get("app_key", ""),
            secret_key=config.get("secret_key", ""),
            redirect_uri=config.get("redirect_uri", "http://localhost:8765/api/v1/storage/cloud/callback"),
        )
    return None


# ============================================================
# Baidu Cloud (百度网盘) Connector
# ============================================================

class BaiduCloudConnector(CloudConnector):
    """Baidu Wangpan (百度网盘) API connector.

    Uses Baidu OAuth 2.0 for authentication.
    API docs: https://pan.baidu.com/union/doc/
    """

    BASE_URL = "https://pan.baidu.com/rest/2.0"
    AUTH_URL = "https://openapi.baidu.com/oauth/2.0"
    OAUTH_AUTHORIZE = "https://openapi.baidu.com/oauth/2.0/authorize"
    OAUTH_TOKEN = "https://openapi.baidu.com/oauth/2.0/token"

    def __init__(self, app_key: str = "", secret_key: str = "", redirect_uri: str = ""):
        super().__init__()
        self._app_key = app_key
        self._secret_key = secret_key
        self._redirect_uri = redirect_uri
        self._config = {"app_key": app_key}

    # ── Auth ────────────────────────────────────────

    async def get_auth_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": self._app_key,
            "redirect_uri": self._redirect_uri,
            "scope": "basic,netdisk",
            "display": "page",
        }
        return f"{self.OAUTH_AUTHORIZE}?{urllib.parse.urlencode(params)}"

    async def handle_callback(self, code: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.OAUTH_TOKEN, params={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._app_key,
                "client_secret": self._secret_key,
                "redirect_uri": self._redirect_uri,
            })
            if resp.status_code != 200:
                return False
            data = resp.json()
            self._access_token = data.get("access_token", "")
            self._refresh_token = data.get("refresh_token", "")
            return bool(self._access_token)

    async def authorize(self, auth_code: str | None = None) -> str:
        if auth_code:
            ok = await self.handle_callback(auth_code)
            return "authenticated" if ok else "auth_failed"
        return await self.get_auth_url()

    # ── Connection ──────────────────────────────────

    async def connect(self, config: dict) -> bool:
        self._app_key = config.get("app_key", self._app_key)
        self._secret_key = config.get("secret_key", self._secret_key)
        self._redirect_uri = config.get("redirect_uri", self._redirect_uri)
        self._access_token = config.get("access_token", self._access_token)
        self._refresh_token = config.get("refresh_token", self._refresh_token)
        return await self.is_available()

    async def disconnect(self) -> None:
        self._access_token = ""
        self._refresh_token = ""

    async def is_available(self) -> bool:
        if not self._access_token:
            return False
        try:
            info = await self._api_call("userinfo")
            return "errno" not in info or info.get("errno") == 0
        except Exception:
            return False

    # ── Scan ────────────────────────────────────────

    async def scan(
        self, root_path: str = "/", recursive: bool = True,
        file_types: list[str] | None = None, progress_callback=None,
    ) -> list[ScannedFile]:
        self._ensure_auth()
        files = await self._list_all_files(root_path, recursive)
        result = []
        total = len(files)
        for i, f in enumerate(files):
            if not is_supported_file(f.get("server_filename", "")):
                continue
            result.append(ScannedFile(
                path=f.get("path", ""),
                name=f.get("server_filename", ""),
                size_bytes=int(f.get("size", 0)),
                modified_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(f.get("server_mtime", 0)))),
                content_type=infer_content_type(f.get("server_filename", "")),
            ))
            if progress_callback:
                await progress_callback(i + 1, total)
        return result

    async def _list_all_files(self, folder: str, recursive: bool) -> list[dict]:
        """Recursively list all supported files."""
        all_files = []
        page = 1
        while True:
            resp = await self._api_call("filelist", {
                "dir": folder,
                "start": (page - 1) * 100,
                "limit": 100,
                "order": "name",
            })
            entries = resp.get("list", [])
            if not entries:
                break
            for entry in entries:
                if entry.get("isdir") == 1 and recursive:
                    sub_files = await self._list_all_files(entry["path"], recursive)
                    all_files.extend(sub_files)
                else:
                    all_files.append(entry)
            if len(entries) < 100:
                break
            page += 1
        return all_files

    async def list_files(self, folder: str = "/") -> list[dict]:
        self._ensure_auth()
        return await self._list_all_files(folder, recursive=False)

    # ── File Operations ─────────────────────────────

    async def read_file(self, file_path: str) -> bytes:
        self._ensure_auth()
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
        try:
            ok = await self.download_file(file_path, tmp.name)
            if ok:
                with open(tmp.name, "rb") as f:
                    return f.read()
            return b""
        finally:
            import os
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    async def download_file(self, remote_path: str, local_path: str) -> bool:
        self._ensure_auth()
        meta = await self._api_call("filemetas", {
            "path": remote_path,
            "dlink": 1,
        })
        dlink = None
        for info in meta.get("info", []):
            if "dlink" in info:
                dlink = info["dlink"]
                break

        if not dlink:
            return False

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                dlink,
                params={"access_token": self._access_token},
                follow_redirects=True,
                timeout=300,
            )
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                return True
        return False

    async def write_file(self, file_path: str, content: bytes) -> bool:
        self._ensure_auth()
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
        try:
            tmp.write(content)
            tmp.close()
            size = os.path.getsize(tmp.name)
            # Step 1: precreate
            pre = await self._api_call("precreate", {
                "path": file_path,
                "size": size,
                "rtype": 3,  # overwrite
                "isdir": 0,
            })
            uploadid = pre.get("uploadid", "")
            if not uploadid:
                return False
            # Step 2: upload in chunks (simplified: single chunk for files < 4MB)
            if size < 4 * 1024 * 1024:
                with open(tmp.name, "rb") as f:
                    file_content = f.read()
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.BASE_URL}/xpan/file?method=upload&access_token={self._access_token}",
                        data={"uploadid": uploadid, "path": file_path},
                        files={"file": (os.path.basename(file_path), file_content)},
                    )
                return resp.status_code == 200
            return False
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    async def delete_file(self, file_path: str) -> bool:
        self._ensure_auth()
        resp = await self._api_call("filemanager", {
            "opera": "delete",
            "async": 0,
            "filelist": json.dumps([file_path]),
        })
        return resp.get("errno", -1) == 0

    # ── Cloud-specific ──────────────────────────────

    async def list_shared(self) -> list[ScannedFile]:
        self._ensure_auth()
        resp = await self._api_call("sharedfile", {"page": 1, "num": 100})
        items = resp.get("list", [])
        return [
            ScannedFile(
                path=f.get("path", ""),
                name=f.get("server_filename", ""),
                size_bytes=int(f.get("size", 0)),
                content_type=infer_content_type(f.get("server_filename", "")),
            )
            for f in items if is_supported_file(f.get("server_filename", ""))
        ]

    async def get_download_url(self, file_path: str) -> str:
        self._ensure_auth()
        meta = await self._api_call("filemetas", {"path": file_path, "dlink": 1})
        for info in meta.get("info", []):
            if "dlink" in info:
                return f"{info['dlink']}?access_token={self._access_token}"
        return ""

    # ── Info ────────────────────────────────────────

    async def get_info(self) -> StorageInfo:
        if not self._access_token:
            return StorageInfo(
                id="baidu", name="百度网盘", type=StorageType.CLOUD_BAIDU,
                status=StorageStatus.OFFLINE, error_message="未授权",
            )
        try:
            info = await self._api_call("userinfo")
            quota = info.get("quota_info", {})
            total = int(quota.get("total", 0)) / (1024**3)
            used = int(quota.get("used", 0)) / (1024**3)
            return StorageInfo(
                id="baidu",
                name=f"百度网盘 ({info.get('baidu_name', '')})",
                type=StorageType.CLOUD_BAIDU,
                status=StorageStatus.ONLINE,
                total_size_gb=round(total, 1),
                used_size_gb=round(used, 1),
                free_size_gb=round(total - used, 1),
            )
        except Exception as e:
            return StorageInfo(
                id="baidu", name="百度网盘", type=StorageType.CLOUD_BAIDU,
                status=StorageStatus.ERROR, error_message=str(e),
            )

    # ── API Helper ──────────────────────────────────

    async def _api_call(self, method: str, params: dict | None = None) -> dict:
        params = params or {}
        params["method"] = method
        params["access_token"] = self._access_token
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.BASE_URL}/xpan/file", params=params)
            return resp.json() if resp.status_code == 200 else {"errno": -1, "error": resp.text}
