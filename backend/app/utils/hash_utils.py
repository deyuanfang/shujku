import hashlib
from pathlib import Path


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file's content."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_addressed_path(base_dir: Path, file_hash: str) -> Path:
    """Return content-addressed storage path: base_dir/{first2}/{full_hash}"""
    sub_dir = base_dir / file_hash[:2]
    sub_dir.mkdir(parents=True, exist_ok=True)
    return sub_dir / file_hash
