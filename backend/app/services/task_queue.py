"""Background task queue for async LLM analysis.

Uses asyncio queues to process analysis tasks without blocking the HTTP response.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import async_session
from app.database.models import Document, Summary
from app.services.llm_client import analyze_document
from app.services.knowledge_graph import update_knowledge_graph

logger = logging.getLogger(__name__)

# Task queue
_task_queue: asyncio.Queue = asyncio.Queue()
_worker_task: asyncio.Task | None = None
_running = False


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def start_worker():
    """Start the background analysis worker with auto-restart."""
    global _worker_task, _running
    if _running:
        return
    _running = True

    async def _worker_wrapper():
        while _running:
            try:
                await _analysis_worker()
            except Exception as e:
                logger.error(f"Analysis worker crashed: {e}, restarting in 2s...")
                await asyncio.sleep(2)

    _worker_task = asyncio.create_task(_worker_wrapper())
    logger.info("Analysis worker started")


async def stop_worker():
    """Stop the background analysis worker."""
    global _running
    _running = False
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("Analysis worker stopped")


async def enqueue_analysis(document_id: str, title: str, content: str):
    """Add a document to the analysis queue."""
    await _task_queue.put({
        "document_id": document_id,
        "title": title,
        "content": content,
    })
    logger.info(f"Enqueued analysis for document: {document_id}")


async def _analysis_worker():
    """Worker loop — processes analysis tasks with retry."""
    while _running:
        try:
            try:
                task = await asyncio.wait_for(_task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            document_id = task["document_id"]
            title = task["title"]
            content = task["content"]

            success = False
            for attempt in range(3):
                logger.info(f"AI analysis [{document_id[:8]}] attempt {attempt+1}/3")
                llm_result = await analyze_document(
                    title=title, content=content,
                    tasks=["summarize", "extract_entities", "extract_relationships", "suggest_tags"],
                )
                if "error" not in llm_result:
                    success = True
                    break
                if attempt < 2:
                    await asyncio.sleep(5)

            if success:
                async with async_session() as db:
                    try:
                        await _store_analysis_results(db, document_id, llm_result)
                        await db.commit()
                        logger.info(f"AI analysis complete: {document_id[:8]}")
                    except Exception as e:
                        await db.rollback()
                        logger.error(f"Store failed: {e}")
            else:
                logger.warning(f"AI analysis failed after 3 attempts: {document_id[:8]}")

            _task_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker error: {e}")


async def _store_analysis_results(
    db: AsyncSession,
    document_id: str,
    llm_result: dict,
):
    """Store LLM analysis results in the database."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        return

    now = _now()

    # Store summary
    if llm_result.get("summary"):
        # Check for existing summary
        sum_result = await db.execute(
            select(Summary).where(
                Summary.target_type == "document",
                Summary.target_id == document_id,
            )
        )
        existing = sum_result.scalar_one_or_none()

        key_points = llm_result.get("key_points", [])
        tokens = llm_result.get("summary_tokens", {})

        if existing:
            existing.summary_text = llm_result["summary"]
            existing.key_points = str(key_points)
            existing.created_at = now
        else:
            summary = Summary(
                id=str(uuid.uuid4()),
                target_type="document",
                target_id=document_id,
                summary_text=llm_result["summary"],
                key_points=str(key_points),
                model="claude",
                prompt_tokens=tokens.get("prompt", 0),
                completion_tokens=tokens.get("completion", 0),
                created_at=now,
            )
            db.add(summary)

    # Update knowledge graph with entities, relationships, tags
    await update_knowledge_graph(db, document, llm_result)

    # Store summary and keywords directly on the document for frontend access
    if llm_result.get("summary"):
        import json as _json
        document.summary = _json.dumps({"summary": llm_result["summary"], "key_points": llm_result.get("key_points", [])}, ensure_ascii=False)
    if llm_result.get("suggested_tags"):
        import json as _json
        document.keywords = _json.dumps(llm_result["suggested_tags"], ensure_ascii=False)

    # Update document's importance based on entity count
    entity_count = len(llm_result.get("entities", []))
    if entity_count > 0:
        document.importance = min(1.0, 0.3 + entity_count * 0.05)

    document.last_analyzed_at = now
    document.updated_at = now
