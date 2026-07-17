"""Image Analysis Parser — OCR + visual description using AI."""

from pathlib import Path
import base64
import logging

logger = logging.getLogger(__name__)


async def parse_image_enhanced(file_path: Path, use_ai: bool = True) -> dict:
    """Analyze an image: extract text via OCR, generate visual description via AI.

    Returns:
        dict with: title, raw_text (OCR), ocr_text, visual_description,
                   dominant_colors, width, height, format
    """
    result = {
        "title": file_path.stem,
        "raw_text": "",
        "ocr_text": "",
        "visual_description": "",
        "dominant_colors": [],
        "width": 0,
        "height": 0,
        "format": "",
        "error": None,
    }

    # ── Basic image info ──────────────────────────
    try:
        from PIL import Image
        img = Image.open(file_path)
        result["width"] = img.width
        result["height"] = img.height
        result["format"] = img.format or file_path.suffix.upper().lstrip(".")

        # Dominant colors (simple palette extraction)
        try:
            img_small = img.resize((50, 50), Image.LANCZOS)
            colors = img_small.getcolors(maxcolors=10)
            if colors:
                colors.sort(reverse=True)
                result["dominant_colors"] = [
                    f"#{r:02x}{g:02x}{b:02x}"
                    for _count, (r, g, b) in colors[:5]
                ]
        except Exception:
            pass
    except ImportError:
        result["error"] = "Pillow not installed"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result

    # ── OCR text extraction ───────────────────────
    ocr_parts = []
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
        ocr_result = ocr.ocr(str(file_path), cls=True)
        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                text = line[1][0]
                ocr_parts.append(text)
    except ImportError:
        ocr_parts.append("[需安装 PaddleOCR 进行文字识别]")
    except Exception as e:
        ocr_parts.append(f"[OCR 识别失败: {e}]")

    result["ocr_text"] = "\n".join(ocr_parts)
    result["raw_text"] = result["ocr_text"]

    # ── AI Visual Description ─────────────────────
    if use_ai and result["ocr_text"]:
        try:
            desc = await _describe_image_with_ai(file_path, result["ocr_text"])
            if desc:
                result["visual_description"] = desc
                result["raw_text"] = f"[图片描述]\n{desc}\n\n[OCR文字]\n{result['ocr_text']}"
        except Exception as e:
            logger.warning(f"AI image description skipped: {e}")

    result["char_count"] = len(result["raw_text"])
    result["word_count"] = len(result["raw_text"].split())

    return result


# ── AI Image Description ──────────────────────────

async def _describe_image_with_ai(file_path: Path, ocr_text: str) -> str:
    """Use AI to describe the visual content of an image."""
    from app.services.ai_provider import get_provider

    provider = get_provider()
    if not provider or not await provider.is_available():
        return ""

    # Encode image as base64
    with open(file_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Determine image type
    ext = file_path.suffix.lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext.lstrip("."), "jpeg")

    system = "你是一个图片分析助手。用中文简短描述图片的视觉内容和场景。"
    prompt = f"请用2-3句话描述这张图片的视觉内容（场景、主体、氛围）。\n图片中的文字内容: {ocr_text[:200] if ocr_text else '(无文字)'}"

    try:
        # For providers that support vision (Anthropic, OpenAI)
        response = await provider.chat(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": f"image/{mime}",
                        "data": img_b64,
                    }},
                ],
            }],
            max_tokens=300, temperature=0.3,
        )
        return response.text.strip() if response.text else ""
    except Exception:
        # Fallback: text-only description request
        try:
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"{prompt}\n(图片文件: {file_path.name}, {file_path.stat().st_size // 1024}KB)"},
                ],
                max_tokens=200, temperature=0.3,
            )
            return response.text.strip() if response.text else ""
        except Exception:
            pass

    return ""
