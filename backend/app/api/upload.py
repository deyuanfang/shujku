"""Upload API — handles file/text/URL ingestion."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.database.models import Document, Category
from app.services.content_extractor import extract_content, detect_content_type
from app.services.file_handler import save_upload_file
from app.services.nlp_pipeline import nlp_pipeline
from app.utils.hash_utils import compute_text_hash

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _enqueue_if_text(doc: Document, text: str):
    """Enqueue document for async LLM analysis."""
    from app.services.task_queue import enqueue_analysis
    import asyncio
    asyncio.create_task(enqueue_analysis(doc.id, doc.title, text))


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file (text, markdown, PDF, image) for analysis."""
    content_type = detect_content_type(file.filename)

    # Save file
    saved_path, file_hash = await save_upload_file(file)

    # Check for duplicates
    result = await db.execute(
        select(Document).where(Document.original_hash == file_hash)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "status": "duplicate",
            "message": "该文件已存在，无需重复上传",
            "document_id": existing.id,
        }

    # Extract content
    extracted = await extract_content(content_type=content_type, file_path=saved_path)
    raw_text = extracted["raw_text"]

    # NLP analysis
    cat_result = await db.execute(select(Category))
    categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
    classification = nlp_pipeline.classify(raw_text, categories)

    # Create document
    doc = Document(
        id=str(uuid.uuid4()),
        title=title or extracted["title"],
        content_type=content_type,
        source_path=str(saved_path),
        original_hash=file_hash,
        raw_text=raw_text,
        word_count=extracted.get("word_count", 0),
        char_count=extracted.get("char_count", 0),
        category_id=classification["category_id"],
        created_at=_now(),
        updated_at=_now(),
        last_analyzed_at=_now(),
    )
    db.add(doc)

    if classification["category_id"]:
        cat_result = await db.execute(
            select(Category).where(Category.id == classification["category_id"])
        )
        category = cat_result.scalar_one_or_none()
        if category:
            category.document_count += 1

    await db.flush()

    # Enqueue async LLM analysis
    _enqueue_if_text(doc, raw_text)

    return {
        "status": "ok",
        "document_id": doc.id,
        "title": doc.title,
        "content_type": content_type,
        "category": classification["category_name"],
        "confidence": classification["confidence"],
        "keywords": classification["keywords"],
    }


@router.post("/url")
async def upload_url(
    url: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Submit a URL for content extraction."""
    content_type = "url"

    extracted = await extract_content(content_type=content_type, url=url)

    if extracted.get("error"):
        raise HTTPException(status_code=400, detail=extracted["error"])

    raw_text = extracted["raw_text"]
    text_hash = compute_text_hash(raw_text)

    result = await db.execute(
        select(Document).where(Document.original_hash == text_hash)
    )
    if (existing := result.scalar_one_or_none()):
        return {
            "status": "duplicate",
            "message": "该网页内容已存在",
            "document_id": existing.id,
        }

    cat_result = await db.execute(select(Category))
    categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
    classification = nlp_pipeline.classify(raw_text, categories)

    doc = Document(
        id=str(uuid.uuid4()),
        title=extracted["title"],
        content_type=content_type,
        source_url=url,
        original_hash=text_hash,
        raw_text=raw_text,
        word_count=extracted.get("word_count", 0),
        char_count=extracted.get("char_count", 0),
        category_id=classification["category_id"],
        created_at=_now(),
        updated_at=_now(),
        last_analyzed_at=_now(),
    )
    db.add(doc)

    if classification["category_id"]:
        cat_result = await db.execute(
            select(Category).where(Category.id == classification["category_id"])
        )
        if category := cat_result.scalar_one_or_none():
            category.document_count += 1

    await db.flush()

    _enqueue_if_text(doc, raw_text)

    return {
        "status": "ok",
        "document_id": doc.id,
        "title": doc.title,
        "content_type": content_type,
        "category": classification["category_name"],
        "confidence": classification["confidence"],
        "keywords": classification["keywords"],
    }


@router.post("/note")
async def upload_note(
    text: str = Form(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Submit a quick text note."""
    content_type = "note"
    text_hash = compute_text_hash(text)

    result = await db.execute(
        select(Document).where(Document.original_hash == text_hash)
    )
    if (existing := result.scalar_one_or_none()):
        return {
            "status": "duplicate",
            "message": "相同笔记已存在",
            "document_id": existing.id,
        }

    cat_result = await db.execute(select(Category))
    categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
    classification = nlp_pipeline.classify(text, categories)

    doc = Document(
        id=str(uuid.uuid4()),
        title=title or (text[:50] + ("..." if len(text) > 50 else "")),
        content_type=content_type,
        original_hash=text_hash,
        raw_text=text,
        word_count=len(text.split()),
        char_count=len(text),
        category_id=classification["category_id"],
        created_at=_now(),
        updated_at=_now(),
        last_analyzed_at=_now(),
    )
    db.add(doc)

    if classification["category_id"]:
        cat_result = await db.execute(
            select(Category).where(Category.id == classification["category_id"])
        )
        if category := cat_result.scalar_one_or_none():
            category.document_count += 1

    await db.flush()

    # Enqueue async LLM analysis — uses 'text' directly, not 'extracted'
    _enqueue_if_text(doc, text)

    return {
        "status": "ok",
        "document_id": doc.id,
        "title": doc.title,
        "content_type": content_type,
        "category": classification["category_name"],
        "confidence": classification["confidence"],
        "keywords": classification["keywords"],
    }
