"""Knowledge Query API — AI-oriented interface for querying the knowledge base.

Provides RAG-style context retrieval optimized for LLM consumption.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, or_, func

from app.database.connection import get_db
from app.database.models import Document, Category, Entity, DocumentEntity

router = APIRouter()


class KnowledgeQuery(BaseModel):
    query: str
    max_results: int = 5
    include_content: bool = True
    max_content_chars: int = 2000
    filter_category: Optional[str] = None
    filter_type: Optional[str] = None


@router.post("/query")
async def query_knowledge(req: KnowledgeQuery, db: AsyncSession = Depends(get_db)):
    """AI-facing endpoint: search the knowledge base and return LLM-ready context.

    Returns ranked documents with snippets, metadata, and full content if requested.
    Designed as a RAG retrieval endpoint for AI assistants.
    """
    results = []

    # Try FTS5 full-text search first
    # Convert query to FTS5 OR syntax for multi-word queries
    fts_query = _to_fts_query(req.query)
    try:
        fts_result = await db.execute(
            text("""
                SELECT d.id, d.title, d.content_type, d.category_id, d.raw_text,
                       d.word_count, d.importance, d.created_at, d.updated_at,
                       snippet(documents_fts, 1, '', '', '...', 40) as snippet
                FROM documents_fts
                JOIN documents d ON d.rowid = documents_fts.rowid
                WHERE documents_fts MATCH :query AND d.is_active = 1
                ORDER BY rank
                LIMIT :limit
            """),
            {"query": fts_query, "limit": req.max_results * 2},
        )
        rows = fts_result.fetchall()

        for row in rows:
            doc_id, title, ctype, cat_id, raw_text, wc, imp, created, updated, snippet = row
            if req.filter_type and ctype != req.filter_type:
                continue
            if req.filter_category and cat_id != req.filter_category:
                continue
            results.append(_build_result(
                doc_id, title, ctype, cat_id, raw_text, wc, imp, created, updated,
                snippet, req,
            ))
    except Exception:
        pass  # FTS5 may not be initialized

    # Fallback: LIKE search (handles multi-word queries by splitting)
    if len(results) < req.max_results:
        import re
        terms = re.findall(r'[\w]+', req.query)
        if not terms:
            terms = [req.query]

        like_conditions = []
        for term in terms:
            like_conditions.append(Document.title.contains(term))
            like_conditions.append(Document.raw_text.contains(term))

        like_result = await db.execute(
            select(Document).where(
                Document.is_active == 1,
                or_(*like_conditions),
            ).limit(req.max_results * 2)
        )
        for doc in like_result.scalars().all():
            if doc.id not in {r["id"] for r in results}:
                snippet = _make_snippet(doc.raw_text or "", terms[0] if terms else req.query, 80)
                results.append(_build_result(
                    doc.id, doc.title, doc.content_type, doc.category_id,
                    doc.raw_text, doc.word_count, doc.importance,
                    doc.created_at, doc.updated_at, snippet, req,
                ))

    # Get category names
    cat_ids = {r["category_id"] for r in results if r.get("category_id")}
    if cat_ids:
        cat_result = await db.execute(
            select(Category.id, Category.name).where(Category.id.in_(cat_ids))
        )
        cat_map = {row[0]: row[1] for row in cat_result.fetchall()}
        for r in results:
            if r.get("category_id"):
                r["category_name"] = cat_map.get(r["category_id"], "")

    # Get related entities for each document
    for r in results[:5]:
        ent_result = await db.execute(
            select(Entity.name, Entity.type)
            .join(DocumentEntity, DocumentEntity.entity_id == Entity.id)
            .where(DocumentEntity.document_id == r["id"])
            .limit(5)
        )
        r["entities"] = [{"name": row[0], "type": row[1]} for row in ent_result.fetchall()]

    return {
        "query": req.query,
        "results": results[:req.max_results],
        "total_found": len(results),
        "context_ready": _format_for_llm(results[:req.max_results]),
    }


@router.get("/context")
async def get_context(
    q: str = Query(..., min_length=1),
    max_results: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Simplified GET endpoint for quick context retrieval.
    Returns plain text context block ready for LLM prompt injection.
    """
    req = KnowledgeQuery(query=q, max_results=max_results)
    result = await query_knowledge(req, db)
    return {
        "query": q,
        "context": result["context_ready"],
        "source_count": len(result["results"]),
        "sources": [
            {"id": r["id"], "title": r["title"], "relevance": r["relevance"]}
            for r in result["results"]
        ],
    }


@router.get("/related/{doc_id}")
async def get_related(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Find documents related to the given one via shared entities and keywords."""
    # Get the document's entities
    ent_result = await db.execute(
        select(Entity.id).join(DocumentEntity).where(DocumentEntity.document_id == doc_id)
    )
    entity_ids = [row[0] for row in ent_result.fetchall()]

    if not entity_ids:
        return {"document_id": doc_id, "related": []}

    # Find other documents sharing those entities
    rel_result = await db.execute(
        select(Document.id, Document.title, Document.content_type,
               func.count(DocumentEntity.entity_id).label("shared_count"))
        .join(DocumentEntity, DocumentEntity.document_id == Document.id)
        .where(
            DocumentEntity.entity_id.in_(entity_ids),
            Document.id != doc_id,
            Document.is_active == 1,
        )
        .group_by(Document.id)
        .order_by(func.count(DocumentEntity.entity_id).desc())
        .limit(10)
    )
    related = [
        {
            "id": row[0], "title": row[1], "content_type": row[2],
            "shared_entities": row[3],
        }
        for row in rel_result.fetchall()
    ]

    return {"document_id": doc_id, "related": related}


# ── Helpers ─────────────────────────────────────────

def _build_result(doc_id, title, ctype, cat_id, raw_text, wc, imp, created, updated, snippet, req):
    return {
        "id": doc_id,
        "title": title,
        "content_type": ctype,
        "category_id": cat_id,
        "snippet": snippet,
        "word_count": wc,
        "relevance": round(imp or 0.5, 2),
        "created_at": created,
        "updated_at": updated,
        "content": (raw_text or "")[:req.max_content_chars] if req.include_content else None,
    }


def _to_fts_query(query: str) -> str:
    """Convert a natural query into FTS5-compatible OR syntax."""
    # Split Chinese+English words, join with OR
    import re
    words = re.findall(r'[一-鿿]+|[a-zA-Z0-9]+', query)
    if len(words) <= 1:
        return query
    return " OR ".join(words)


def _make_snippet(text: str, query: str, context_chars: int = 80) -> str:
    idx = text.lower().find(query.lower())
    if idx >= 0:
        start = max(0, idx - context_chars // 2)
        end = min(len(text), idx + len(query) + context_chars // 2)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet
    return text[:context_chars * 2] + ("..." if len(text) > context_chars * 2 else "")


def _format_for_llm(results: list[dict]) -> str:
    """Format search results into a context block for LLM prompt injection."""
    if not results:
        return "未找到相关知识库内容。"

    parts = ["以下是知识库中与查询相关的文档内容：\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"--- 文档 {i}: {r['title']} ---")
        parts.append(f"类型: {r['content_type']} | 字数: {r['word_count']} | 相关度: {r['relevance']}")
        if r.get("category_name"):
            parts.append(f"分类: {r['category_name']}")
        if r.get("entities"):
            parts.append(f"相关实体: {', '.join(e['name'] for e in r['entities'])}")
        parts.append(f"摘要: {r['snippet']}")
        if r.get("content"):
            parts.append(f"\n完整内容:\n{r['content']}")
        parts.append("")

    return "\n".join(parts)
