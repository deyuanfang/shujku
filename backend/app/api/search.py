"""Search API — full-text search across documents."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, or_

from app.database.connection import get_db
from app.database.models import Document

router = APIRouter()
_fts5_initialized = False


async def _ensure_fts5(db: AsyncSession):
    """Lazily create FTS5 virtual table on first search."""
    global _fts5_initialized
    if _fts5_initialized:
        return
    try:
        from app.database.models import FTS5_SETUP_SQL
        for stmt in FTS5_SETUP_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await db.execute(text(stmt + ";"))
                except Exception:
                    pass
        await db.commit()
        _fts5_initialized = True
    except Exception:
        pass


@router.get("")
async def search_documents(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across documents using FTS5 and LIKE fallback."""
    await _ensure_fts5(db)
    results = []
    total = 0

    # Try FTS5 first
    try:
        count_result = await db.execute(
            text(
                "SELECT count(*) FROM documents_fts "
                "WHERE documents_fts MATCH :query"
            ),
            {"query": q},
        )
        total = count_result.scalar() or 0

        if total > 0:
            search_result = await db.execute(
                text(
                    "SELECT d.id, d.title, d.content_type, d.category_id, "
                    "d.created_at, d.word_count, "
                    "snippet(documents_fts, 1, '<mark>', '</mark>', '...', 60) as snippet "
                    "FROM documents_fts "
                    "JOIN documents d ON d.rowid = documents_fts.rowid "
                    "WHERE documents_fts MATCH :query "
                    "ORDER BY rank "
                    "LIMIT :limit OFFSET :offset"
                ),
                {
                    "query": q,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            )
            for row in search_result.fetchall():
                results.append({
                    "id": row[0],
                    "title": row[1],
                    "content_type": row[2],
                    "category_id": row[3],
                    "created_at": row[4],
                    "word_count": row[5],
                    "snippet": row[6] if len(row) > 6 else "",
                })
    except Exception:
        pass  # FTS5 may not be initialized yet

    # Fallback: LIKE search
    if not results:
        like_pattern = f"%{q}%"
        count_query = select(Document).where(
            Document.is_active == 1,
            or_(
                Document.title.contains(q),
                Document.raw_text.contains(q),
            ),
        )
        result = await db.execute(
            select(Document).where(
                Document.is_active == 1,
                or_(
                    Document.title.contains(q),
                    Document.raw_text.contains(q),
                ),
            )
        )
        docs = result.scalars().all()
        total = len(docs)

        offset = (page - 1) * page_size
        for doc in docs[offset:offset + page_size]:
            # Generate a simple snippet
            snippet = ""
            if doc.raw_text:
                idx = doc.raw_text.find(q)
                if idx >= 0:
                    start = max(0, idx - 30)
                    end = min(len(doc.raw_text), idx + len(q) + 30)
                    snippet = ("..." if start > 0 else "") + doc.raw_text[start:end] + ("..." if end < len(doc.raw_text) else "")
                else:
                    snippet = doc.raw_text[:100]

            results.append({
                "id": doc.id,
                "title": doc.title,
                "content_type": doc.content_type,
                "category_id": doc.category_id,
                "created_at": doc.created_at,
                "word_count": doc.word_count,
                "snippet": snippet,
            })

    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "query": q,
    }
