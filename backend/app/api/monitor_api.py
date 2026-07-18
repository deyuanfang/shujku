"""AI Action Logs & Folder Watcher API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database.connection import get_db
from app.services.ai_action_logger import AIActionLog
from app.services.folder_watcher import start_watcher, stop_watcher, WATCHED_DIRS

router = APIRouter()


# ── AI Action Logs ────────────────────────────────

@router.get("/ai-logs")
async def get_ai_logs(
    document_id: str | None = Query(None),
    status: str | None = Query(None),
    action_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Query AI action logs with optional filters."""
    query = select(AIActionLog).order_by(desc(AIActionLog.created_at))

    if document_id:
        query = query.where(AIActionLog.document_id == document_id)
    if status:
        query = query.where(AIActionLog.status == status)
    if action_type:
        query = query.where(AIActionLog.action_type == action_type)

    result = await db.execute(query.limit(limit))
    logs = result.scalars().all()

    return {
        "total": len(logs),
        "logs": [
            {
                "id": log.id,
                "document_id": log.document_id,
                "action_type": log.action_type,
                "provider": log.provider,
                "model": log.model,
                "status": log.status,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "duration_ms": log.duration_ms,
                "error_message": log.error_message,
                "result_summary": log.result_summary,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }


@router.get("/ai-logs/stats")
async def get_ai_log_stats(db: AsyncSession = Depends(get_db)):
    """Get summary statistics of AI actions."""
    total = await db.execute(select(func.count()).select_from(AIActionLog))
    success = await db.execute(
        select(func.count()).where(AIActionLog.status == "success")
    )
    failed = await db.execute(
        select(func.count()).where(AIActionLog.status == "failed")
    )
    total_tokens = await db.execute(
        select(func.sum(AIActionLog.input_tokens + AIActionLog.output_tokens))
    )

    return {
        "total_actions": total.scalar() or 0,
        "success": success.scalar() or 0,
        "failed": failed.scalar() or 0,
        "total_tokens": total_tokens.scalar() or 0,
    }


# ── Folder Watcher ────────────────────────────────

@router.get("/watcher/status")
async def get_watcher_status():
    """Get folder watcher status."""
    from app.services.folder_watcher import _running
    return {
        "running": _running,
        "watched_dirs": WATCHED_DIRS,
        "scan_interval_seconds": 10,
    }


@router.post("/watcher/start")
async def start_folder_watcher(dirs: str = Query("")):
    """Start the folder watcher. Optionally specify comma-separated directories."""
    directories = [d.strip() for d in dirs.split(",") if d.strip()] if dirs else []

    if not directories:
        # Default: watch Desktop, Documents, Downloads
        import os
        home = os.path.expanduser("~")
        directories = [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Downloads"),
        ]
        directories = [d for d in directories if os.path.isdir(d)]

    from app.services.folder_watcher import start_watcher
    await start_watcher(directories)

    return {
        "status": "started",
        "watched_dirs": WATCHED_DIRS,
        "scan_interval_seconds": 10,
    }


@router.post("/watcher/stop")
async def stop_folder_watcher():
    """Stop the folder watcher."""
    await stop_watcher()
    return {"status": "stopped"}
