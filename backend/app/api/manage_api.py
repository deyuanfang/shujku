"""Document management API — delete, clear all, remote clear with auth key."""

import os
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database.connection import get_db
from app.database.models import (
    Document, DocumentVersion, Category, Entity, Tag, DocumentTag,
    DocumentEntity, Relationship, KnowledgeNode, KnowledgeEdge,
    Summary, ChangeLog, Alert, Setting,
)
from app.services.ai_action_logger import AIActionLog

router = APIRouter()

# Remote clear key — generate once on first start
_clear_key_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", ".clear_key")


def _get_clear_key() -> str:
    """Get or create the remote clear API key."""
    os.makedirs(os.path.dirname(_clear_key_file), exist_ok=True)
    if os.path.exists(_clear_key_file):
        return open(_clear_key_file).read().strip()
    key = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    with open(_clear_key_file, "w") as f:
        f.write(key)
    return key


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ── Delete single document ─────────────────────────

@router.delete("/manage/doc/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Permanently delete a document and all related data."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "文档不存在")

    title = doc.title

    # Delete related data
    await db.execute(delete(DocumentVersion).where(DocumentVersion.document_id == doc_id))
    await db.execute(delete(DocumentTag).where(DocumentTag.document_id == doc_id))
    await db.execute(delete(DocumentEntity).where(DocumentEntity.document_id == doc_id))
    await db.execute(delete(ChangeLog).where(ChangeLog.document_id == doc_id))
    await db.execute(delete(Summary).where(Summary.target_id == doc_id, Summary.target_type == "document"))
    await db.execute(delete(AIActionLog).where(AIActionLog.document_id == doc_id))

    # Update category count
    if doc.category_id:
        cat_result = await db.execute(select(Category).where(Category.id == doc.category_id))
        if cat := cat_result.scalar_one_or_none():
            cat.document_count = max(0, cat.document_count - 1)

    await db.delete(doc)
    await db.flush()

    return {"status": "ok", "message": f"已删除: {title}", "document_id": doc_id}


# ── Clear all documents ────────────────────────────

@router.post("/manage/clear-all")
async def clear_all_documents(
    confirm: str = Query(""),
    remote_key: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Clear ALL documents. Requires confirmation text or remote key.

    Local: confirm must be "确认清空所有数据"
    Remote: provide the remote_key from GET /manage/clear-key
    """
    expected_key = _get_clear_key()

    # Auth: either local confirmation phrase or remote key
    if confirm == "确认清空所有数据":
        pass  # local confirmation
    elif remote_key and remote_key == expected_key:
        pass  # remote key auth
    else:
        raise HTTPException(403, "需要确认短语或远程密钥。获取密钥: GET /api/v1/manage/clear-key")

    # Count before delete
    doc_count = (await db.execute(select(Document))).scalars().all()
    total = len(doc_count)

    # Delete all related data
    await db.execute(delete(DocumentVersion))
    await db.execute(delete(DocumentTag))
    await db.execute(delete(DocumentEntity))
    await db.execute(delete(ChangeLog))
    await db.execute(delete(Alert))
    await db.execute(delete(Summary))
    await db.execute(delete(Relationship))
    await db.execute(delete(AIActionLog))
    await db.execute(delete(KnowledgeEdge))
    await db.execute(delete(KnowledgeNode))
    await db.execute(delete(Entity))
    await db.execute(delete(Tag))
    await db.execute(delete(Document))

    # Reset category counts
    cats = (await db.execute(select(Category))).scalars().all()
    for cat in cats:
        cat.document_count = 0

    await db.flush()

    return {
        "status": "ok",
        "message": f"已清空所有数据",
        "deleted_documents": total,
        "timestamp": _now(),
    }


# ── Remote clear key ───────────────────────────────

@router.get("/manage/clear-key")
async def get_clear_key():
    """Get the remote clear API key. Requires local access."""
    return {
        "clear_key": _get_clear_key(),
        "usage": f"POST /api/v1/manage/clear-all?remote_key={_get_clear_key()}",
        "warning": "此密钥可远程清空所有数据，请妥善保管",
    }


# ── Batch delete ───────────────────────────────────

@router.post("/manage/batch-delete")
async def batch_delete_documents(
    doc_ids: str = Query(...),  # comma-separated
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple documents at once."""
    ids = [i.strip() for i in doc_ids.split(",") if i.strip()]
    deleted = 0
    for doc_id in ids:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        if doc := result.scalar_one_or_none():
            await db.execute(delete(DocumentVersion).where(DocumentVersion.document_id == doc_id))
            await db.execute(delete(DocumentTag).where(DocumentTag.document_id == doc_id))
            await db.execute(delete(DocumentEntity).where(DocumentEntity.document_id == doc_id))
            if doc.category_id:
                cat_result = await db.execute(select(Category).where(Category.id == doc.category_id))
                if cat := cat_result.scalar_one_or_none():
                    cat.document_count = max(0, cat.document_count - 1)
            await db.delete(doc)
            deleted += 1

    await db.flush()
    return {"status": "ok", "deleted": deleted, "total_requested": len(ids)}
