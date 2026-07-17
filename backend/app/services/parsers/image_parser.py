"""Parse images using OCR (PaddleOCR)."""

from pathlib import Path


async def parse_image_file(file_path: Path) -> dict:
    """Extract text from an image using OCR."""
    raw_text = ""
    error = None

    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang="ch", use_angle_cls=True)
        result = ocr.ocr(str(file_path), cls=True)

        lines = []
        if result and result[0]:
            for line_info in result[0]:
                text = line_info[1][0]
                lines.append(text)
        raw_text = "\n".join(lines)
    except ImportError:
        error = "PaddleOCR not installed"
        raw_text = f"[图片 OCR 需要安装 PaddleOCR: {file_path.name}]"
    except Exception as e:
        error = str(e)
        raw_text = f"[OCR 识别失败: {e}]"

    return {
        "title": file_path.stem,
        "raw_text": raw_text,
        "char_count": len(raw_text),
        "word_count": len(raw_text.split()),
        "error": error,
    }
