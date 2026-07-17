"""Dispatch content extraction to the appropriate parser."""

from pathlib import Path
from app.services.parsers.text_parser import parse_text_file
from app.services.parsers.pdf_parser_enhanced import parse_pdf_enhanced
from app.services.parsers.image_parser_enhanced import parse_image_enhanced
from app.services.parsers.video_parser import parse_video
from app.services.parsers.web_scraper import parse_url


# Extension → content type mapping
EXT_MAPPING = {
    ".txt": "text", ".md": "markdown", ".markdown": "markdown",
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".bmp": "image", ".webp": "image", ".tiff": "image",
    ".mp4": "video", ".avi": "video", ".mkv": "video",
    ".mov": "video", ".webm": "video", ".flv": "video",
    ".wmv": "video", ".m4v": "video",
    ".doc": "pdf", ".docx": "pdf", ".ppt": "pdf", ".pptx": "pdf",
    ".csv": "text", ".json": "text", ".xml": "text",
}

SUPPORTED_EXTENSIONS = set(EXT_MAPPING.keys())


async def extract_content(
    content_type: str,
    file_path: Path | None = None,
    url: str | None = None,
    note_text: str | None = None,
) -> dict:
    """Route content extraction to the correct parser based on type."""

    if content_type == "note":
        return {
            "title": note_text[:50] if note_text else "快速笔记",
            "raw_text": note_text or "",
            "char_count": len(note_text) if note_text else 0,
            "word_count": len(note_text.split()) if note_text else 0,
        }

    if content_type == "url":
        return await parse_url(url)

    if file_path is None:
        raise ValueError("file_path is required for file-based content")

    if content_type in ("text", "markdown"):
        return await parse_text_file(file_path)

    if content_type == "pdf":
        return await parse_pdf_enhanced(file_path)

    if content_type == "image":
        return await parse_image_enhanced(file_path)

    if content_type == "video":
        return await parse_video(file_path)

    raise ValueError(f"Unsupported content type: {content_type}")


def detect_content_type(filename: str | None, url: str | None = None) -> str:
    """Infer content type from file extension or input type."""
    if url:
        return "url"
    if filename is None:
        return "note"
    ext = Path(filename).suffix.lower()
    return EXT_MAPPING.get(ext, "text")
