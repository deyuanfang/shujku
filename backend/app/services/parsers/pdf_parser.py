"""Parse PDF files using PyMuPDF."""

from pathlib import Path


async def parse_pdf_file(file_path: Path) -> dict:
    """Extract text from a PDF file."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {
            "title": file_path.stem,
            "raw_text": f"[PDF 解析需要安装 PyMuPDF: {file_path.name}]",
            "char_count": 0,
            "word_count": 0,
            "error": "PyMuPDF not installed",
        }

    doc = fitz.open(str(file_path))
    full_text = []
    title = file_path.stem

    for page in doc:
        text = page.get_text()
        if text.strip():
            full_text.append(text)

    doc.close()
    raw_text = "\n\n".join(full_text)

    return {
        "title": title,
        "raw_text": raw_text,
        "char_count": len(raw_text),
        "word_count": len(raw_text.replace("\n", " ").split()),
    }
