"""Parse plain text and markdown files."""

from pathlib import Path


async def parse_text_file(file_path: Path) -> dict:
    """Extract plain text from .txt or .md files."""
    content = file_path.read_text(encoding="utf-8")

    # Try to extract title from first heading, otherwise use filename
    title = file_path.name  # keep full filename
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return {
        "title": title,
        "raw_text": content,
        "char_count": len(content),
        "word_count": len(content.replace("\n", " ").split()),
    }
