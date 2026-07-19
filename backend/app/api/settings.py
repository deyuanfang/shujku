"""Settings API — read/write user settings stored in the settings table."""

import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from datetime import datetime, timezone

from app.database.connection import get_db
from app.database.models import Setting
from app.config import settings as app_settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    ollama_url: Optional[str] = None
    auto_analyze: Optional[bool] = None
    language: Optional[str] = None
    theme: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all settings as a flat dict."""
    result = await db.execute(select(Setting))
    rows = result.scalars().all()

    settings_dict = {}
    for row in rows:
        try:
            settings_dict[row.key] = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            settings_dict[row.key] = row.value

    # Merge with defaults
    defaults = {
        "llm_api_key": app_settings.llm_api_key,
        "llm_model": app_settings.llm_model,
        "auto_analyze": app_settings.auto_analyze,
        "language": app_settings.language,
        "theme": app_settings.theme,
    }
    defaults.update(settings_dict)
    return defaults


@router.put("")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Bulk update settings."""
    data = body.model_dump(exclude_none=True)

    for key, value in data.items():
        json_value = json.dumps(value, ensure_ascii=False)

        # Upsert
        result = await db.execute(select(Setting).where(Setting.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = json_value
            existing.updated_at = _now()
        else:
            setting = Setting(key=key, value=json_value, updated_at=_now())
            db.add(setting)

        # Update runtime config
        if key == "llm_api_key":
            app_settings.llm_api_key = value or ""
        elif key == "llm_model" and value:
            app_settings.llm_model = value
        elif key == "auto_analyze":
            app_settings.auto_analyze = bool(value)

    # After saving all settings, try to configure the AI provider
    await _configure_from_db(db)

    return {"status": "ok", "message": "设置已保存"}


async def _configure_from_db(db: AsyncSession):
    """Read settings from DB and configure the active AI provider."""
    try:
        from app.services.ai_provider import configure_provider
        all_rows = (await db.execute(select(Setting))).scalars().all()
        db_settings = {}
        for row in all_rows:
            try:
                db_settings[row.key] = json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                db_settings[row.key] = row.value

        prov = db_settings.get("llm_provider", "")
        key = db_settings.get("llm_api_key", "")
        model = db_settings.get("llm_model", "")
        url = db_settings.get("ollama_url", "")

        if prov and (key or prov == "ollama"):
            config = {"api_key": key, "model": model}
            if url:
                config["base_url"] = url
            configure_provider(prov, config)
            import logging
            logging.getLogger(__name__).info(f"AI provider configured from settings: {prov}")
    except Exception:
        pass
