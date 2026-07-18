"""Data Organizer API — manual triggers for the AI 数据整理大师."""

import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.connection import get_db
from app.database.models import Document, Category, Entity
from app.services.data_organizer import (
    organize_new_document, review_categories, generate_cross_topic_insights,
)
from app.services.ai_provider import list_providers, get_provider, configure_provider
from app.config import settings

router = APIRouter()


# ⚠️ Fixed routes MUST come before parameterized routes

@router.get("/providers")
async def get_ai_providers():
    """List available AI providers and their models."""
    providers = list_providers()
    current = get_provider()
    return {
        "providers": providers,
        "current_provider": current.name if current else None,
        "current_model": current.model if current else None,
    }


@router.post("/configure")
async def configure_ai(provider: str = Query(...), api_key: str = Query(""),
                        model: str = Query(""), base_url: str = Query("")):
    """Configure and test the AI provider. Returns detailed status."""
    config = {"api_key": api_key, "model": model}
    if base_url: config["base_url"] = base_url

    # Quick validation
    if provider != "ollama" and not api_key:
        return {"status": "error", "message": "请输入 API Key", "available": False}

    # Try to create and test provider
    error_detail = ""
    try:
        p = configure_provider(provider, config)
    except ValueError as e:
        return {"status": "error", "message": f"不支持的提供商: {provider}", "available": False}

    # Test availability with timeout
    import asyncio
    try:
        available = await asyncio.wait_for(p.is_available(), timeout=15.0)
    except asyncio.TimeoutError:
        return {"status": "error", "message": "连接超时(15秒),请检查网络或API Key", "available": False, "provider": provider, "model": p.model}
    except Exception as e:
        error_detail = str(e)[:200]
        return {"status": "error", "message": f"连接失败: {error_detail}", "available": False, "provider": provider, "model": p.model}

    if available:
        # Also save to settings table so it persists
        try:
            from app.database.connection import async_session
            from sqlalchemy import text
            import json
            async with async_session() as db:
                for key, val in [("llm_provider", provider), ("llm_api_key", api_key), ("llm_model", model)]:
                    json_val = json.dumps(val, ensure_ascii=False)
                    await db.execute(
                        text("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (:k, :v, datetime('now'))"),
                        {"k": key, "v": json_val})
                await db.commit()
        except Exception:
            pass

        return {"status": "ok", "provider": provider, "model": p.model, "available": True, "message": f"✅ {provider}/{p.model} 连接成功"}
    else:
        return {"status": "error", "message": f"连接验证失败: {provider}/{p.model} 返回异常,请检查API Key", "available": False, "provider": provider, "model": p.model}


@router.post("/review-categories")
async def review_category_structure(db: AsyncSession = Depends(get_db)):
    """AI reviews the entire category structure and suggests improvements."""
    cats = (await db.execute(select(Category))).scalars().all()
    cat_data = [{"name": c.name, "document_count": c.document_count} for c in cats]
    result = await review_categories(cat_data)
    return {"status": "ok", "result": result}


@router.post("/insights")
async def cross_topic_insights(db: AsyncSession = Depends(get_db)):
    """Generate cross-topic insights across the knowledge base."""
    cats = (await db.execute(select(Category))).scalars().all()
    ents = (await db.execute(select(Entity).order_by(Entity.mention_count.desc()).limit(20))).scalars().all()
    result = await generate_cross_topic_insights(
        [{"name": c.name} for c in cats], [{"name": e.name} for e in ents],
    )
    return {"status": "ok", "result": result}


@router.post("/{doc_id}")
async def organize_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger the Data Organizer on a specific document."""
    result = await db.execute(select(Document).where(Document.id == doc_id, Document.is_active == 1))
    doc = result.scalar_one_or_none()
    if not doc:
        return {"status": "error", "message": "文档不存在"}
    if not doc.raw_text:
        return {"status": "error", "message": "文档无文本内容"}

    # Gather context
    cats = (await db.execute(select(Category))).scalars().all()
    ents = (await db.execute(select(Entity))).scalars().all()
    docs = (await db.execute(
        select(Document).where(Document.is_active == 1, Document.id != doc_id)
        .order_by(Document.updated_at.desc()).limit(10)
    )).scalars().all()

    org_result = await organize_new_document(
        title=doc.title, content=doc.raw_text,
        existing_categories=[{"name": c.name, "document_count": c.document_count} for c in cats],
        existing_entities=[{"name": e.name, "type": e.type} for e in ents],
        recent_documents=[{"title": d.title} for d in docs],
    )

    # Store results
    if org_result.get("classification", {}).get("suggested_category") and not doc.category_id:
        suggested = org_result["classification"]["suggested_category"]
        cat_result = await db.execute(select(Category).where(Category.name == suggested))
        if not (existing_cat := cat_result.scalar_one_or_none()):
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            existing_cat = Category(id=str(uuid.uuid4()), name=suggested, color="#6366f1",
                                     document_count=0, created_at=now, updated_at=now)
            db.add(existing_cat); await db.flush()
        doc.category_id = existing_cat.id
        existing_cat.document_count += 1

    if org_result.get("summary"):
        doc.summary = json.dumps(org_result["summary"], ensure_ascii=False)
    if org_result.get("entities"):
        doc.keywords = json.dumps([e["name"] for e in org_result["entities"]], ensure_ascii=False)
    if org_result.get("quality"):
        doc.importance = org_result["quality"].get("importance", 0.5)

    doc.last_analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db.flush()

    return {"status": "ok", "document_id": doc_id, "result": org_result}
