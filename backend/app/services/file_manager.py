"""Local File Manager — scan, deduplicate, organize files on disk.

Operates directly on the filesystem:
- Deep scan directories with content hashing
- Find duplicate files by SHA-256
- Auto-organize by type/date/category
- Move/copy/symlink management
"""

import os
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# File categories for auto-organization
FILE_CATEGORIES = {
    "文档": [".txt", ".md", ".markdown", ".doc", ".docx", ".pdf", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".odt"],
    "图片": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".psd", ".raw"],
    "视频": [".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".3gp"],
    "音频": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"],
    "代码": [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".rs", ".go", ".rb", ".php", ".sql", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".toml"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "可执行": [".exe", ".msi", ".app", ".dmg", ".deb", ".rpm", ".apk"],
    "其他": [],
}


def categorize_file(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for cat, exts in FILE_CATEGORIES.items():
        if ext in exts:
            return cat
    return "其他"


@dataclass
class FileEntry:
    path: str           # absolute path
    name: str           # filename
    size: int           # bytes
    modified: str       # ISO date
    category: str       # 文档/图片/视频/...
    hash: str = ""      # SHA-256 (populated on deep scan)
    is_duplicate: bool = False
    duplicate_of: str = ""  # path of the original file


@dataclass
class ScanResult:
    total_files: int = 0
    total_size: int = 0
    duplicates: list[list[FileEntry]] = field(default_factory=list)  # groups of duplicates
    duplicate_count: int = 0
    wasted_bytes: int = 0
    by_category: dict = field(default_factory=lambda: defaultdict(list))
    by_date: dict = field(default_factory=lambda: defaultdict(list))  # YYYY-MM → files
    files: list[FileEntry] = field(default_factory=list)


def _compute_hash(filepath: str, quick=False) -> str:
    """Compute SHA-256 hash. If quick=True, hash only first 64KB + file size."""
    h = hashlib.sha256()
    try:
        stat = os.stat(filepath)
        if quick:
            h.update(str(stat.st_size).encode())
            with open(filepath, "rb") as f:
                h.update(f.read(65536))
        else:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return ""


async def scan_directory(
    root: str,
    recursive: bool = True,
    deep: bool = False,     # compute full hashes
    progress=None,          # async callback(current, total)
) -> ScanResult:
    """Scan a directory and return file analysis results."""
    result = ScanResult()
    root_path = Path(root).resolve()

    if not root_path.exists():
        return result

    # Collect all files
    all_files = []
    if recursive:
        for dirpath, _, filenames in os.walk(root_path):
            for fname in filenames:
                all_files.append(Path(dirpath) / fname)
    else:
        all_files = [p for p in root_path.iterdir() if p.is_file()]

    total = len(all_files)
    result.total_files = total

    # Hash index for dedup
    hash_index: dict[str, list[FileEntry]] = defaultdict(list)

    for i, filepath in enumerate(all_files):
        try:
            stat = filepath.stat()
            entry = FileEntry(
                path=str(filepath),
                name=filepath.name,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                category=categorize_file(filepath.name),
            )
            result.total_size += stat.st_size
            result.by_category[entry.category].append(entry)
            date_key = entry.modified[:7]  # YYYY-MM
            result.by_date[date_key].append(entry)

            if deep:
                entry.hash = _compute_hash(str(filepath))
                if entry.hash:
                    if entry.hash in hash_index:
                        entry.is_duplicate = True
                        entry.duplicate_of = hash_index[entry.hash][0].path
                    hash_index[entry.hash].append(entry)

            result.files.append(entry)
        except (PermissionError, OSError):
            continue

        if progress:
            await progress(i + 1, total)

    # Find duplicate groups
    for h, entries in hash_index.items():
        if len(entries) > 1:
            result.duplicates.append(entries)
            result.duplicate_count += len(entries) - 1  # extras beyond first
            # Wasted space = all copies except the first
            for dup in entries[1:]:
                result.wasted_bytes += dup.size

    return result


async def organize_files(
    root: str,
    target: str = "",
    strategy: str = "category",  # category | date | flat
    action: str = "copy",        # copy | move | symlink
    dry_run: bool = True,
) -> dict:
    """Organize files into folders by category or date.

    Args:
        root: Source directory to organize.
        target: Target directory (default: root/.organized).
        strategy: "category" or "date" grouping.
        action: "copy", "move", or "symlink".
        dry_run: If True, only return plan without executing.
    """
    root_path = Path(root).resolve()
    if not target:
        target = str(root_path / ".organized")
    target_path = Path(target).resolve()

    if target_path == root_path or str(target_path).startswith(str(root_path) + os.sep):
        target_path = root_path / "_organized"

    plan = {"files": [], "folders_created": [], "total_size": 0}

    for dirpath, _, filenames in os.walk(root_path):
        # Skip target directory
        if str(target_path) in str(Path(dirpath).resolve()):
            continue
        for fname in filenames:
            src = Path(dirpath) / fname
            cat = categorize_file(fname)
            if strategy == "date":
                mtime = datetime.fromtimestamp(src.stat().st_mtime)
                dest_dir = target_path / mtime.strftime("%Y-%m")
            elif strategy == "flat":
                dest_dir = target_path
            else:  # category
                dest_dir = target_path / cat

            dest = dest_dir / fname

            # Handle name conflicts
            counter = 1
            while dest.exists() and not dry_run:
                stem, ext = os.path.splitext(fname)
                dest = dest_dir / f"{stem}_{counter}{ext}"
                counter += 1

            plan["files"].append({
                "source": str(src),
                "destination": str(dest),
                "category": cat,
                "size": src.stat().st_size,
            })
            plan["total_size"] += src.stat().st_size

            if str(dest_dir) not in plan["folders_created"]:
                plan["folders_created"].append(str(dest_dir))

    if not dry_run:
        for item in plan["files"]:
            os.makedirs(os.path.dirname(item["destination"]), exist_ok=True)
            src, dst = item["source"], item["destination"]
            if action == "move":
                shutil.move(src, dst)
            elif action == "symlink":
                if os.path.exists(dst): os.remove(dst)
                os.symlink(src, dst)
            else:  # copy
                shutil.copy2(src, dst)

    return plan


async def delete_duplicates(
    root: str,
    dry_run: bool = True,
) -> dict:
    """Find and optionally delete duplicate files. Keeps the first copy."""
    scan = await scan_directory(root, recursive=True, deep=True)
    deleted = []
    freed_bytes = 0

    for dup_group in scan.duplicates:
        for dup in dup_group[1:]:  # skip first (original)
            deleted.append({"path": dup.path, "size": dup.size, "original": dup_group[0].path})
            freed_bytes += dup.size
            if not dry_run:
                try:
                    os.remove(dup.path)
                except OSError:
                    pass

    return {
        "duplicate_groups": len(scan.duplicates),
        "duplicate_files": len(deleted),
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "deleted": deleted[:100],
        "dry_run": dry_run,
    }
