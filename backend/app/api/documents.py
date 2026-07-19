"""Documents API — CRUD for knowledge items."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database.connection import get_db
from app.database.models import Document, Category
from app.schemas.document import DocumentResponse, DocumentDetailResponse

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@router.get("")
async def list_documents(
    category_id: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    """List documents with optional filters and pagination."""
    query = select(Document).where(Document.is_active == 1)

    if category_id:
        query = query.where(Document.category_id == category_id)
    if content_type:
        query = query.where(Document.content_type == content_type)

    # Full-text search via FTS5
    if search:
        fts_query = select(Document.id).where(
            or_(
                Document.title.contains(search),
                Document.raw_text.contains(search),
            )
        )
        # Also try FTS5
        try:
            from sqlalchemy import text
            fts_result = await db.execute(
                text(
                    "SELECT rowid FROM documents_fts WHERE documents_fts MATCH :q"
                ),
                {"q": search},
            )
            fts_ids = [row[0] for row in fts_result.fetchall()]
            if fts_ids:
                query = query.where(Document.id.in_(fts_ids))
        except Exception:
            pass  # FTS may not be set up yet, fall through to LIKE search

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(Document, sort_by, Document.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    items = [
        DocumentResponse(
            id=doc.id,
            title=doc.title,
            content_type=doc.content_type,
            source_path=doc.source_path,
            source_url=doc.source_url,
            original_hash=doc.original_hash,
            word_count=doc.word_count,
            char_count=doc.char_count,
            category_id=doc.category_id,
            importance=doc.importance,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            last_analyzed_at=doc.last_analyzed_at,
        )
        for doc in documents
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document with full content."""
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.is_active == 1,
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    return DocumentDetailResponse(
        id=doc.id,
        title=doc.title,
        content_type=doc.content_type,
        source_path=doc.source_path,
        source_url=doc.source_url,
        original_hash=doc.original_hash,
        raw_text=doc.raw_text,
        summary=doc.summary,
        word_count=doc.word_count,
        char_count=doc.char_count,
        category_id=doc.category_id,
        importance=doc.importance,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        last_analyzed_at=doc.last_analyzed_at,
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a document."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Update category count
    if doc.category_id:
        cat_result = await db.execute(
            select(Category).where(Category.id == doc.category_id)
        )
        category = cat_result.scalar_one_or_none()
        if category:
            category.document_count = max(0, category.document_count - 1)

    doc.is_active = 0
    doc.updated_at = _now()

    return {"status": "ok", "message": "文档已删除"}


@router.post("/{doc_id}/version")
async def upload_new_version(
    doc_id: str,
    text: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new version of an existing document. Triggers change detection."""
    from app.database.models import DocumentVersion, ChangeLog, Alert
    from app.services.change_detector import detect_changes
    from app.utils.hash_utils import compute_text_hash
    from app.services.task_queue import enqueue_analysis
    import json

    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    new_hash = compute_text_hash(text)
    if new_hash == doc.original_hash:
        return {"status": "no_change", "message": "内容未发生变化"}

    # Detect changes
    old_keywords = json.loads(doc.keywords) if doc.keywords else None
    if isinstance(old_keywords, str):
        try:
            old_keywords = json.loads(old_keywords)
        except json.JSONDecodeError:
            old_keywords = []

    changes = detect_changes(
        old_text=doc.raw_text or "",
        new_text=text,
        old_keywords=old_keywords,
    )

    # Create version record
    version_count_result = await db.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == doc_id)
    )
    version_count = len(version_count_result.scalars().all())

    old_version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        version_number=version_count + 1,
        source_hash=doc.original_hash,
        raw_text=doc.raw_text,
        word_count=doc.word_count,
        char_count=doc.char_count,
        created_at=_now(),
    )
    db.add(old_version)

    new_version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        version_number=version_count + 2,
        source_hash=new_hash,
        raw_text=text,
        word_count=len(text.split()),
        char_count=len(text),
        created_at=_now(),
    )
    db.add(new_version)
    await db.flush()

    # Create change log
    change_log = ChangeLog(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        old_version_id=old_version.id,
        new_version_id=new_version.id,
        severity=changes["severity_score"],
        severity_label=changes["severity_label"],
        content_diff=changes["diff_summary"],
        entity_changes=json.dumps({
            "added_keywords": changes.get("added_keywords", []),
            "removed_keywords": changes.get("removed_keywords", []),
        }, ensure_ascii=False),
        is_confirmed=0 if changes["severity_label"] in ("major", "significant") else 1,
        created_at=_now(),
    )
    db.add(change_log)

    # If major or significant change, create an alert
    if changes["severity_label"] in ("major", "significant"):
        alert = Alert(
            id=str(uuid.uuid4()),
            title=f"文档内容重大变更: {doc.title}",
            message=f"变更严重程度: {changes['severity_label']}\n{changes['diff_summary']}",
            alert_type="change",
            related_item_id=doc_id,
            severity="high" if changes["severity_label"] == "major" else "medium",
            created_at=_now(),
        )
        db.add(alert)
        # Don't auto-update the document — wait for user confirmation
        await db.flush()
        return {
            "status": "pending_confirmation",
            "change_log_id": change_log.id,
            "severity": changes["severity_label"],
            "severity_score": changes["severity_score"],
            "diff_summary": changes["diff_summary"],
            "diff_snippet": changes["diff_snippet"],
            "message": "检测到重大变更，请确认后再更新",
        }

    # Auto-update for minor/moderate changes
    doc.raw_text = text
    doc.original_hash = new_hash
    doc.word_count = len(text.split())
    doc.char_count = len(text)
    doc.updated_at = _now()
    doc.keywords = json.dumps(changes.get("new_keywords", []), ensure_ascii=False)

    # Enqueue re-analysis
    await enqueue_analysis(doc.id, doc.title, text)

    await db.flush()

    return {
        "status": "auto_updated",
        "change_log_id": change_log.id,
        "severity": changes["severity_label"],
        "severity_score": changes["severity_score"],
        "diff_summary": changes["diff_summary"],
        "message": f"变更已自动更新 ({changes['severity_label']})",
    }


@router.post("/{doc_id}/reanalyze")
async def reanalyze_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger re-analysis of a document."""
    from app.services.task_queue import enqueue_analysis

    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    if not doc.raw_text:
        raise HTTPException(status_code=400, detail="文档无文本内容")

    await enqueue_analysis(doc.id, doc.title, doc.raw_text)

    return {
        "status": "queued",
        "document_id": doc_id,
        "message": "分析任务已加入队列",
    }
