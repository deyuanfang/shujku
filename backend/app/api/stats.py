"""Stats API — dashboard statistics."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.connection import get_db
from app.database.models import Document, Category, Entity

router = APIRouter()


@router.get("")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard overview statistics."""
    # Total documents
    doc_count_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.is_active == 1)
    )
    total_docs = doc_count_result.scalar() or 0

    # Total categories
    cat_count_result = await db.execute(
        select(func.count()).select_from(Category)
    )
    total_categories = cat_count_result.scalar() or 0

    # Total entities
    ent_count_result = await db.execute(
        select(func.count()).select_from(Entity)
    )
    total_entities = ent_count_result.scalar() or 0

    # Documents by content type
    type_result = await db.execute(
        select(
            Document.content_type,
            func.count(Document.id),
        )
        .where(Document.is_active == 1)
        .group_by(Document.content_type)
    )
    docs_by_type = {row[0]: row[1] for row in type_result.fetchall()}

    # Total words
    words_result = await db.execute(
        select(func.sum(Document.word_count))
        .where(Document.is_active == 1)
    )
    total_words = words_result.scalar() or 0

    # Documents by category (top 5)
    cat_docs_result = await db.execute(
        select(Category.name, Category.document_count)
        .order_by(Category.document_count.desc())
        .limit(5)
    )
    top_categories = [
        {"name": row[0], "count": row[1]}
        for row in cat_docs_result.fetchall()
    ]

    return {
        "total_documents": total_docs,
        "total_categories": total_categories,
        "total_entities": total_entities,
        "total_words": total_words,
        "documents_by_type": docs_by_type,
        "top_categories": top_categories,
    }
