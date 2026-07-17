"""Enhanced PDF Parser — extracts text, TOC, metadata, and embedded images."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


async def parse_pdf_enhanced(file_path: Path) -> dict:
    """Extract text, table of contents, and metadata from a PDF.

    Returns:
        dict with: title, raw_text, pages, toc, metadata, images_count
    """
    result = {
        "title": file_path.stem,
        "raw_text": "",
        "pages": 0,
        "toc": [],
        "metadata": {},
        "images_count": 0,
        "error": None,
    }

    try:
        import fitz  # PyMuPDF
    except ImportError:
        result["error"] = "PyMuPDF not installed. Run: pip install PyMuPDF"
        return result

    try:
        doc = fitz.open(str(file_path))
        result["pages"] = len(doc)

        # Metadata
        meta = doc.metadata
        result["metadata"] = {
            "author": meta.get("author", ""),
            "title": meta.get("title", file_path.stem),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "format": meta.get("format", ""),
            "page_count": len(doc),
        }
        if meta.get("title"):
            result["title"] = meta["title"]

        # Table of contents
        toc = doc.get_toc(simple=True)
        if toc:
            result["toc"] = [
                {"level": level, "title": title, "page": page}
                for level, title, page in toc
            ]

        # Extract text page by page
        full_text_parts = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                full_text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")

            # Count embedded images
            images = page.get_images()
            result["images_count"] += len(images)

        result["raw_text"] = "\n\n".join(full_text_parts)
        result["char_count"] = len(result["raw_text"])
        result["word_count"] = len(result["raw_text"].replace("\n", " ").split())

        # If TOC exists, prepend it to the text for better classification
        if result["toc"]:
            toc_text = "目录结构:\n" + "\n".join(
                f"{'  ' * (t['level'] - 1)}- {t['title']}"
                for t in result["toc"]
            )
            result["raw_text"] = toc_text + "\n\n" + result["raw_text"]

        doc.close()

    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        result["error"] = str(e)

    return result
