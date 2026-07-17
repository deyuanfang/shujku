"""Video Analysis Parser — extract metadata, subtitles, keyframes from videos."""

from pathlib import Path
import subprocess
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

SUPPORTED_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v"}


async def parse_video(file_path: Path) -> dict:
    """Analyze a video file: metadata, subtitles, keyframe OCR.

    Requires ffmpeg/ffprobe installed on the system.
    """
    result = {
        "title": file_path.stem,
        "raw_text": "",
        "duration_seconds": 0,
        "resolution": "",
        "codec": "",
        "fps": 0,
        "bitrate": "",
        "subtitles_text": "",
        "has_subtitles": False,
        "keyframe_descriptions": [],
        "error": None,
    }

    # ── Check ffprobe ──────────────────────────────
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        result["error"] = "需要安装 ffmpeg/ffprobe。下载: https://ffmpeg.org/"
        return result

    # ── Extract metadata via ffprobe ───────────────
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams",
             str(file_path)],
            capture_output=True, text=True, timeout=60,
        )
        import json
        info = json.loads(probe.stdout)

        fmt = info.get("format", {})
        result["duration_seconds"] = float(fmt.get("duration", 0))
        result["bitrate"] = f"{int(fmt.get('bit_rate', 0)) // 1000}kbps" if fmt.get("bit_rate") else ""

        for stream in info.get("streams", []):
            if stream["codec_type"] == "video":
                result["codec"] = stream.get("codec_name", "")
                result["fps"] = _parse_fps(stream.get("r_frame_rate", ""))
                result["resolution"] = f"{stream.get('width', 0)}x{stream.get('height', 0)}"
                break

    except Exception as e:
        logger.error(f"ffprobe error: {e}")

    # ── Extract subtitles ──────────────────────────
    srt_text = await _extract_subtitles(file_path)
    if srt_text:
        result["has_subtitles"] = True
        result["subtitles_text"] = srt_text
        result["raw_text"] = srt_text

    # ── Extract keyframes for OCR ──────────────────
    if not result["has_subtitles"] and result["duration_seconds"] > 0:
        try:
            keyframes = await _extract_keyframes(file_path, result["duration_seconds"])
            if keyframes:
                result["keyframe_descriptions"] = keyframes
                text_parts = [f"视频时长: {result['duration_seconds']:.0f}秒",
                              f"分辨率: {result['resolution']}"]
                if keyframes:
                    text_parts.append("关键帧内容: " + " | ".join(keyframes))
                result["raw_text"] = "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Keyframe extraction error: {e}")

    # ── Fallback: metadata-only description ────────
    if not result["raw_text"]:
        parts = [
            f"视频文件: {file_path.name}",
            f"时长: {result['duration_seconds']:.1f}秒",
            f"分辨率: {result['resolution']}",
            f"编码: {result['codec']}",
            f"帧率: {result['fps']}fps" if result['fps'] else "",
        ]
        result["raw_text"] = "\n".join(p for p in parts if p)

    result["char_count"] = len(result["raw_text"])
    result["word_count"] = len(result["raw_text"].split())

    return result


# ── Helpers ───────────────────────────────────────

async def _extract_subtitles(file_path: Path) -> str:
    """Extract embedded subtitles or find external .srt files."""
    # Try embedded subtitles first
    try:
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp:
            tmp_path = tmp.name

        subprocess.run(
            ["ffmpeg", "-y", "-i", str(file_path), "-map", "0:s:0",
             "-f", "srt", tmp_path],
            capture_output=True, timeout=60,
        )

        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 100:
            with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            os.unlink(tmp_path)
            # Clean SRT: remove timestamps and index numbers, keep text
            lines = []
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.isdigit():
                    continue
                if "-->" in line:
                    continue
                lines.append(line)
            return "\n".join(lines)
        else:
            os.unlink(tmp_path)
    except Exception:
        pass

    # Try external .srt file (same name, .srt extension)
    srt_path = file_path.with_suffix(".srt")
    if srt_path.exists():
        try:
            content = srt_path.read_text(encoding="utf-8", errors="replace")
            lines = []
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.isdigit() or "-->" in line:
                    continue
                lines.append(line)
            return "\n".join(lines)
        except Exception:
            pass

    return ""


async def _extract_keyframes(file_path: Path, duration: float) -> list[str]:
    """Extract keyframes and run OCR on them."""
    descriptions = []
    # Extract 3 keyframes at 25%, 50%, 75% of the video
    positions = [duration * pct for pct in [0.25, 0.50, 0.75]]

    for i, pos in enumerate(positions):
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name

            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(pos), "-i", str(file_path),
                 "-vframes", "1", "-q:v", "2", tmp_path],
                capture_output=True, timeout=30,
            )

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 500:
                # Try OCR on the keyframe
                try:
                    from paddleocr import PaddleOCR
                    ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
                    ocr_result = ocr.ocr(tmp_path, cls=True)
                    texts = []
                    if ocr_result and ocr_result[0]:
                        for line in ocr_result[0]:
                            texts.append(line[1][0])
                    if texts:
                        descriptions.append(f"时间{pos:.0f}s: {' '.join(texts[:5])}")
                except ImportError:
                    descriptions.append(f"时间{pos:.0f}s: (需PaddleOCR)")
                except Exception:
                    pass

            os.unlink(tmp_path)
        except Exception:
            pass

    return descriptions


def _parse_fps(rate_str: str) -> float:
    """Parse FPS from ffprobe r_frame_rate (e.g., '30000/1001')."""
    if not rate_str:
        return 0
    try:
        if "/" in rate_str:
            num, den = rate_str.split("/")
            return round(float(num) / float(den), 2)
        return float(rate_str)
    except (ValueError, ZeroDivisionError):
        return 0
