"""Storage abstraction layer — unified interface for all storage backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
import enum


class StorageType(enum.Enum):
    LOCAL = "local"
    NAS = "nas"
    REMOVABLE = "removable"
    CLOUD_BAIDU = "baidu_cloud"
    CLOUD_ALIYUN = "aliyun_cloud"
    CLOUD_ONEDRIVE = "onedrive"


class StorageStatus(enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SCANNING = "scanning"
    ERROR = "error"


@dataclass
class StorageInfo:
    """Metadata about a storage backend."""
    id: str
    name: str
    type: StorageType
    status: StorageStatus = StorageStatus.OFFLINE
    root_path: str = ""
    total_size_gb: float = 0
    used_size_gb: float = 0
    free_size_gb: float = 0
    file_count: int = 0
    last_scan: Optional[str] = None
    config: dict = field(default_factory=dict)
    error_message: str = ""


@dataclass
class ScannedFile:
    """A file discovered during storage scanning."""
    path: str                    # Full path on the storage
    name: str                    # File name
    size_bytes: int = 0
    modified_at: Optional[str] = None
    content_type: str = "text"   # Inferred content type
    hash: str = ""               # SHA-256, populated on import
    is_new: bool = True          # Not yet imported into knowledge base
    is_modified: bool = False    # Modified since last import


class BaseStorage(ABC):
    """Abstract base for all storage backends."""

    @abstractmethod
    async def connect(self, config: dict) -> bool:
        """Establish connection to the storage."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    async def scan(
        self,
        root_path: str = "",
        recursive: bool = True,
        file_types: list[str] | None = None,
        progress_callback=None,
    ) -> list[ScannedFile]:
        """Scan the storage for files. Returns list of discovered files.

        Args:
            root_path: Relative path within storage to start scanning from.
            recursive: Whether to scan subdirectories.
            file_types: Filter by extension, e.g. ['.md', '.txt', '.pdf'].
            progress_callback: Async callable(current, total) for progress.
        """
        ...

    @abstractmethod
    async def read_file(self, file_path: str) -> bytes:
        """Read a file's content from the storage."""
        ...

    @abstractmethod
    async def write_file(self, file_path: str, content: bytes) -> bool:
        """Write content to the storage."""
        ...

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from the storage."""
        ...

    @abstractmethod
    async def get_info(self) -> StorageInfo:
        """Get storage metadata and status."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the storage is currently accessible."""
        ...


class BaseCloudStorage(BaseStorage):
    """Extended interface for cloud storage backends."""

    @abstractmethod
    async def authorize(self, auth_code: str | None = None) -> str:
        """Start OAuth flow or verify token. Returns auth URL or status."""
        ...

    @abstractmethod
    async def list_shared(self) -> list[ScannedFile]:
        """List files shared with the user."""
        ...

    @abstractmethod
    async def get_download_url(self, file_path: str) -> str:
        """Get a temporary download URL for a cloud file."""
        ...


# Supported file extensions for knowledge base scanning
SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.pdf',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
    '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.html', '.htm', '.csv', '.json', '.xml',
}

CONTENT_TYPE_MAP = {
    '.txt': 'text', '.md': 'markdown', '.markdown': 'markdown',
    '.pdf': 'pdf',
    '.png': 'image', '.jpg': 'image', '.jpeg': 'image',
    '.gif': 'image', '.bmp': 'image', '.webp': 'image',
    '.doc': 'pdf', '.docx': 'pdf',
    '.html': 'url', '.htm': 'url',
    '.csv': 'text', '.json': 'text', '.xml': 'text',
}


def infer_content_type(filename: str) -> str:
    """Infer content type from file extension."""
    ext = Path(filename).suffix.lower()
    return CONTENT_TYPE_MAP.get(ext, 'text')


def is_supported_file(filename: str) -> bool:
    """Check if a file type is supported for knowledge base import."""
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS
