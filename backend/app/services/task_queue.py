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
    """Worker loop that processes analysis tasks from the queue."""
    while _running:
        try:
            # Wait for a task (with timeout to allow checking _running)
            try:
                task = await asyncio.wait_for(_task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            document_id = task["document_id"]
            title = task["title"]
            content = task["content"]

            logger.info(f"Starting analysis for: {document_id}")

            # Log: AI action started
            from app.services.ai_action_logger import log_action
            from app.database.connection import async_session as _as
            start_time = __import__("time").time()

            # Run LLM analysis
            llm_result = await analyze_document(
                title=title, content=content,
                tasks=["summarize", "extract_entities", "extract_relationships", "suggest_tags"],
            )

            duration = int((__import__("time").time() - start_time) * 1000)

            # Log: AI action completed
            provider = getattr(getattr(llm_result, 'provider', None), 'name', 'unknown') if hasattr(llm_result, 'provider') else 'auto'
            if "error" not in llm_result:
                await log_action(_as, document_id, "analyze", provider,
                    getattr(settings, 'llm_model', ''), "success",
                    duration_ms=duration,
                    summary=f"summary={'YES' if llm_result.get('summary') else 'NO'}, entities={len(llm_result.get('entities',[]))}, tags={len(llm_result.get('suggested_tags',[]))}"
                )
            else:
                await log_action(_as, document_id, "analyze", "auto", "", "failed",
                    duration_ms=duration, error=llm_result.get("error", ""))

            # Run Data Organizer (数据整理大师)
            organizer_result = None
            try:
                from app.services.data_organizer import organize_new_document
                from app.database.models import Category, Entity, Document as DocModel
                async with async_session() as org_db:
                    cats = (await org_db.execute(select(Category))).scalars().all()
                    ents = (await org_db.execute(select(Entity))).scalars().all()
                    docs = (await org_db.execute(
                        select(DocModel).where(DocModel.is_active == 1).order_by(DocModel.created_at.desc()).limit(10)
                    )).scalars().all()
                    organizer_result = await organize_new_document(
                        title=title, content=content,
                        existing_categories=[{"name": c.name, "document_count": c.document_count} for c in cats],
                        existing_entities=[{"name": e.name, "type": e.type} for e in ents],
                        recent_documents=[{"title": d.title} for d in docs if d.title != title],
                    )
            except Exception as e:
                logger.warning(f"Organizer skipped: {e}")

            if "error" in llm_result:
                logger.warning(f"LLM analysis skipped for {document_id}: {llm_result['error']}")
                _task_queue.task_done()
                continue

            # Store results in database
            async with async_session() as db:
                try:
                    await _store_analysis_results(db, document_id, llm_result)
                    await db.commit()
                    logger.info(f"Analysis complete for: {document_id}")
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Failed to store analysis for {document_id}: {e}")

            _task_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Analysis worker error: {e}")


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

    # Update document's importance based on entity count
    entity_count = len(llm_result.get("entities", []))
    if entity_count > 0:
        document.importance = min(1.0, 0.3 + entity_count * 0.05)

    document.last_analyzed_at = now
    document.updated_at = now
