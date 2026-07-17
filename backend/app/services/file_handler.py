"""Handle file upload and storage."""

import shutil
from pathlib import Path
from fastapi import UploadFile
import aiofiles

from app.config import settings
from app.utils.hash_utils import compute_file_hash, content_addressed_path


async def save_upload_file(upload_file: UploadFile) -> tuple[Path, str]:
    """Save an uploaded file to content-addressed storage.

    Returns:
        Tuple of (storage_path, file_hash)
    """
    # First, save to a temp location to compute hash
    temp_path = settings.upload_dir / f"_temp_{upload_file.filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(temp_path, "wb") as f:
        while chunk := await upload_file.read(8192):
            await f.write(chunk)

    # Compute hash and move to content-addressed location
    file_hash = compute_file_hash(temp_path)
    final_path = content_addressed_path(settings.upload_dir, file_hash)

    if not final_path.exists():
        shutil.move(str(temp_path), str(final_path))
    else:
        temp_path.unlink()  # Duplicate, remove temp

    return final_path, file_hash


async def save_text_as_file(text: str, prefix: str = "note") -> tuple[Path, str]:
    """Save text content as a file. Used for quick notes."""
    from app.utils.hash_utils import compute_text_hash

    file_hash = compute_text_hash(text)
    final_path = content_addressed_path(settings.upload_dir, file_hash)

    if not final_path.exists():
        final_path.write_text(text, encoding="utf-8")

    return final_path, file_hash
