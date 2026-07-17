"""Changes & Alerts API."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.database.models import ChangeLog, Alert

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ── Change Logs ────────────────────────────────────────────

@router.get("/logs")
async def list_change_logs(
    document_id: str | None = Query(None),
    is_confirmed: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List change logs with optional filters."""
    query = select(ChangeLog)
    if document_id:
        query = query.where(ChangeLog.document_id == document_id)
    if is_confirmed is not None:
        query = query.where(ChangeLog.is_confirmed == (1 if is_confirmed else 0))

    query = query.order_by(ChangeLog.created_at.desc())
    offset = (page - 1) * page_size

    result = await db.execute(query.offset(offset).limit(page_size))
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "document_id": log.document_id,
                "severity": log.severity,
                "severity_label": log.severity_label,
                "content_diff": log.content_diff,
                "entity_changes": log.entity_changes,
                "is_confirmed": bool(log.is_confirmed),
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "page": page,
        "page_size": page_size,
    }


@router.post("/logs/{log_id}/confirm")
async def confirm_change(log_id: str, db: AsyncSession = Depends(get_db)):
    """Confirm a change."""
    result = await db.execute(select(ChangeLog).where(ChangeLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        return {"status": "error", "message": "变更记录不存在"}

    log.is_confirmed = 1
    log.confirmed_at = _now()
    return {"status": "ok", "message": "已确认变更"}


@router.post("/logs/{log_id}/dismiss")
async def dismiss_change(log_id: str, db: AsyncSession = Depends(get_db)):
    """Dismiss a change (keep old version)."""
    result = await db.execute(select(ChangeLog).where(ChangeLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        return {"status": "error", "message": "变更记录不存在"}

    log.is_confirmed = 2  # dismissed
    return {"status": "ok", "message": "已忽略变更"}


# ── Alerts ─────────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    is_read: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List alerts/notifications."""
    query = select(Alert).order_by(Alert.created_at.desc())
    if is_read is not None:
        query = query.where(Alert.is_read == (1 if is_read else 0))

    result = await db.execute(query.limit(50))
    alerts = result.scalars().all()

    unread_count = 0
    items = []
    for a in alerts:
        if not a.is_read:
            unread_count += 1
        items.append({
            "id": a.id,
            "title": a.title,
            "message": a.message,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "is_read": bool(a.is_read),
            "related_item_id": a.related_item_id,
            "created_at": a.created_at,
        })

    return {"items": items, "unread_count": unread_count}


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, db: AsyncSession = Depends(get_db)):
    """Mark an alert as read."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert:
        alert.is_read = 1
    return {"status": "ok"}


@router.post("/alerts/read-all")
async def mark_all_alerts_read(db: AsyncSession = Depends(get_db)):
    """Mark all alerts as read."""
    result = await db.execute(select(Alert).where(Alert.is_read == 0))
    for alert in result.scalars().all():
        alert.is_read = 1
    return {"status": "ok"}
