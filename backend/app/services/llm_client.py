"""AI Client — multi-provider document analysis via ai_provider abstraction.

Uses the configured provider (Anthropic/OpenAI/DeepSeek/Ollama) from settings.
Auto-initializes the provider on first use.
"""

import json
import logging
from typing import Optional

from app.services.ai_provider import get_provider, configure_provider, BaseAIProvider
from app.config import settings

logger = logging.getLogger(__name__)


async def _ensure_provider() -> Optional[BaseAIProvider]:
    """Ensure an AI provider is configured and available.

    Priority: DB settings table → config.py → return None
    """
    provider = get_provider()
    if provider and await provider.is_available():
        return provider

    # Try to load from DB settings
    try:
        from app.database.connection import async_session
        from sqlalchemy import text
        async with async_session() as db:
            result = await db.execute(text("SELECT key, value FROM settings WHERE key IN ('llm_provider', 'llm_api_key', 'llm_model', 'ollama_url')"))
            db_settings = {}
            for row in result.fetchall():
                if row[1]:
                    try:
                        db_settings[row[0]] = json.loads(row[1])
                    except (json.JSONDecodeError, TypeError):
                        db_settings[row[0]] = row[1]
            logger.info(f"DB settings loaded: provider={db_settings.get('llm_provider','?')}, key_len={len(db_settings.get('llm_api_key','') or '')}")
    except Exception as e:
        logger.warning(f"Failed to load DB settings: {e}")
        db_settings = {}

    prov_name = db_settings.get("llm_provider", "") or getattr(settings, "llm_provider", None) or "anthropic"
    api_key = db_settings.get("llm_api_key", "") or settings.llm_api_key or ""
    model = db_settings.get("llm_model", "") or settings.llm_model or "claude-sonnet-4-20250514"
    base_url = db_settings.get("ollama_url", "") or ""

    if prov_name != "ollama" and not api_key:
        logger.warning("No AI API key configured. Set API key in Settings page.")
        return None

    config = {"api_key": api_key, "model": model}
    if base_url:
        config["base_url"] = base_url

    try:
        provider = configure_provider(prov_name, config)
        if await provider.is_available():
            logger.info(f"AI provider ready: {prov_name}/{model}")
            return provider
        else:
            logger.warning(f"AI provider not available: {prov_name}")
            return None
    except Exception as e:
        logger.error(f"Failed to configure AI provider: {e}")
        return None


async def analyze_document(
    title: str, content: str, tasks: list[str] | None = None,
) -> dict:
    """Analyze a document using the configured AI provider."""
    provider = await _ensure_provider()
    if not provider:
        return {"error": "AI not configured — set API key in Settings"}

    if tasks is None:
        tasks = ["summarize", "extract_entities", "extract_relationships", "suggest_tags"]

    # Truncate content
    max_chars = 6000
    text = content[:max_chars] + ("\n[...已截断...]" if len(content) > max_chars else "")
    results = {}

    # ── Summarization ──────────────────────────────
    if "summarize" in tasks:
        try:
            response = await provider.chat(
                messages=[{
                    "role": "user",
                    "content": f"""请为以下文档生成简洁摘要（100-200字）和3-5个关键要点。用中文。
标题：{title}
内容：{text}
请用JSON格式：{{"summary":"...","key_points":["要点1","要点2"]}}"""
                }],
                max_tokens=500, temperature=0.3, json_mode=True,
            )
            parsed = _parse_json(response.text)
            results["summary"] = parsed.get("summary", "") if parsed else response.text[:300]
            results["key_points"] = parsed.get("key_points", []) if parsed else []
            results["summary_tokens"] = {"prompt": response.input_tokens, "completion": response.output_tokens}
        except Exception as e:
            logger.error(f"Summarization failed: {e}")

    # ── Entity Extraction ──────────────────────────
    if "extract_entities" in tasks:
        try:
            response = await provider.chat(
                messages=[{
                    "role": "user",
                    "content": f"""提取文档中的命名实体。类型: person/organization/location/concept/event/technology。
标题：{title}
内容：{text}
用JSON数组: [{{"name":"实体","type":"concept","description":"描述"}}] 最多20个。"""
                }],
                max_tokens=800, temperature=0.3, json_mode=True,
            )
            parsed = _parse_json(response.text)
            results["entities"] = parsed if isinstance(parsed, list) else []
            results["entity_tokens"] = {"prompt": response.input_tokens, "completion": response.output_tokens}
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")

    # ── Relationships ──────────────────────────────
    if "extract_relationships" in tasks and results.get("entities"):
        ent_names = [e["name"] for e in results["entities"][:10]]
        try:
            response = await provider.chat(
                messages=[{
                    "role": "user",
                    "content": f"""找出这些实体间的关系: {', '.join(ent_names)}
文档: {text[:1500]}
用JSON数组: [{{"source":"A","target":"B","relation_type":"uses/part_of/related_to","description":"关系"}}]"""
                }],
                max_tokens=500, temperature=0.3, json_mode=True,
            )
            parsed = _parse_json(response.text)
            results["relationships"] = parsed if isinstance(parsed, list) else []
        except Exception as e:
            logger.error(f"Relationships failed: {e}")

    # ── Tag Suggestions ────────────────────────────
    if "suggest_tags" in tasks:
        try:
            response = await provider.chat(
                messages=[{
                    "role": "user",
                    "content": f"""为这篇文档建议3-8个中文标签（2-6字）。
标题：{title}
内容：{text[:1000]}
用JSON数组: ["标签1","标签2"]"""
                }],
                max_tokens=200, temperature=0.3, json_mode=True,
            )
            parsed = _parse_json(response.text)
            results["suggested_tags"] = parsed if isinstance(parsed, list) else []
        except Exception as e:
            logger.error(f"Tags failed: {e}")

    return results


def _parse_json(text: str):
    if not text: return None
    text = text.strip()
    if text.startswith("```"): text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try: return json.loads(text)
    except json.JSONDecodeError:
        import re; m = re.search(r'[\[{].*[}\]]', text, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
    return None
