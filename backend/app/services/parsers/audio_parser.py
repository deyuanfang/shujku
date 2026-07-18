"""Audio Parser — extract text from audio files using transcription.

Supports: local Whisper model, OpenAI Whisper API, or ffmpeg metadata fallback.
"""

from pathlib import Path
import subprocess
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".webm"}


async def parse_audio(file_path: Path) -> dict:
    """Extract text from an audio file via transcription.

    Priority: OpenAI Whisper API → local whisper → metadata fallback
    """
    result = {
        "title": file_path.stem,
        "raw_text": "",
        "duration_seconds": 0,
        "format": file_path.suffix.lower().lstrip("."),
        "transcription_method": "none",
        "error": None,
    }

    # ── Get audio metadata via ffprobe ────────────
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
             str(file_path)],
            capture_output=True, text=True, timeout=30,
        )
        import json
        info = json.loads(probe.stdout)
        fmt = info.get("format", {})
        result["duration_seconds"] = float(fmt.get("duration", 0))
        result["format"] = fmt.get("format_name", result["format"])
    except Exception:
        pass

    # ── Try OpenAI Whisper API ────────────────────
    text = await _transcribe_whisper_api(file_path)
    if text:
        result["raw_text"] = text
        result["transcription_method"] = "whisper_api"
        result["char_count"] = len(text)
        result["word_count"] = len(text)
        return result

    # ── Try local whisper ─────────────────────────
    text = await _transcribe_local_whisper(file_path)
    if text:
        result["raw_text"] = text
        result["transcription_method"] = "local_whisper"
        result["char_count"] = len(text)
        result["word_count"] = len(text)
        return result

    # ── Fallback: metadata only ───────────────────
    dur = result["duration_seconds"]
    result["raw_text"] = f"[音频文件] {file_path.name}\n时长: {dur:.0f}秒\n格式: {result['format']}\n(需要配置Whisper进行语音转文字)"
    result["transcription_method"] = "metadata_fallback"
    result["char_count"] = len(result["raw_text"])
    result["word_count"] = len(result["raw_text"].split())
    result["error"] = "No transcription method available"

    return result


async def _transcribe_whisper_api(file_path: Path) -> str:
    """Try OpenAI Whisper API for transcription."""
    from app.services.ai_provider import get_provider

    provider = get_provider()
    if not provider or not await provider.is_available():
        return ""

    # Only OpenAI provider supports Whisper API natively
    if provider.name not in ("openai", "deepseek"):
        return ""

    try:
        import httpx

        # For OpenAI, use the transcription endpoint
        api_key = getattr(provider, 'api_key', '')
        if not api_key:
            return ""

        async with httpx.AsyncClient(timeout=120) as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, f"audio/{file_path.suffix.lstrip('.')}")}
                headers = {"Authorization": f"Bearer {api_key}"}
                data = {"model": "whisper-1", "language": "zh"}
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers, files=files, data=data,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    return result.get("text", "")
                else:
                    logger.warning(f"Whisper API failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Whisper API error: {e}")

    return ""


async def _transcribe_local_whisper(file_path: Path) -> str:
    """Try local whisper model for transcription."""
    try:
        import whisper
    except ImportError:
        return ""

    try:
        # Use tiny model for speed, run in thread to not block
        import asyncio
        model = await asyncio.to_thread(whisper.load_model, "tiny")
        result = await asyncio.to_thread(
            model.transcribe, str(file_path),
            language="zh", task="transcribe",
            fp16=False,
        )
        text = result.get("text", "").strip()
        if text:
            return text
    except Exception as e:
        logger.warning(f"Local whisper error: {e}")

    return ""
