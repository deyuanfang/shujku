"""Parse plain text and markdown files."""

from pathlib import Path


async def parse_text_file(file_path: Path) -> dict:
    """Extract plain text from .txt or .md files."""
    content = file_path.read_text(encoding="utf-8")

    # Extract title from first heading or filename
    title = file_path.stem
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
