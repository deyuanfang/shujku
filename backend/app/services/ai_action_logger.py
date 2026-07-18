"""AI Action Logger — records every AI analysis attempt with full traceability.

Stores: start time, end time, provider, model, tokens, success/fail, error details.
"""

import uuid
import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, Integer, Float, Text, Index
from app.database.models import Base, gen_uuid

logger = logging.getLogger(__name__)


class AIActionLog(Base):
    """Records every AI analysis action for traceability."""
    __tablename__ = "ai_action_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, nullable=True, index=True)
    action_type = Column(String, nullable=False)  # summarize/classify/extract_entities/organize/insights
    provider = Column(String, nullable=False)     # anthropic/openai/ollama/deepseek/local
    model = Column(String, nullable=True)          # model name
    status = Column(String, default="pending")     # pending/running/success/failed/skipped
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)       # how long the call took
    error_message = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)    # brief summary of what was produced
    created_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_ai_logs_doc", "document_id"),
        Index("idx_ai_logs_status", "status"),
        Index("idx_ai_logs_created", "created_at"),
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class ActionLogger:
    """Context manager for logging AI actions."""

    def __init__(self, db_session_factory, document_id: str, action_type: str,
                 provider: str = "local", model: str = ""):
        self.db_session_factory = db_session_factory
        self.document_id = document_id
        self.action_type = action_type
        self.provider = provider
        self.model = model
        self.log_id: Optional[str] = None
        self.start_time: float = 0
        self.result_data: dict = {}

    async def __aenter__(self):
        self.start_time = time.time()
        self.log_id = str(uuid.uuid4())

        # Create log entry
        log = AIActionLog(
            id=self.log_id,
            document_id=self.document_id,
            action_type=self.action_type,
            provider=self.provider,
            model=self.model,
            status="running",
            created_at=_now(),
        )

        async with self.db_session_factory() as db:
            db.add(log)
            try:
                await db.commit()
            except Exception:
                await db.rollback()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = int((time.time() - self.start_time) * 1000)
        status = "failed" if exc_type else "success"

        async with self.db_session_factory() as db:
            from sqlalchemy import select
            result = await db.execute(select(AIActionLog).where(AIActionLog.id == self.log_id))
            log = result.scalar_one_or_none()
            if log:
                log.status = status
                log.duration_ms = duration
                if exc_val:
                    log.error_message = str(exc_val)[:500]
                if self.result_data:
                    log.input_tokens = self.result_data.get("input_tokens", 0)
                    log.output_tokens = self.result_data.get("output_tokens", 0)
                    summary = self.result_data.get("summary", "")
                    log.result_summary = summary[:300] if summary else ""
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()

            logger.info(
                f"AI Action [{self.action_type}] {status} | "
                f"provider={self.provider} model={self.model} | "
                f"duration={duration}ms tokens={self.result_data.get('input_tokens',0)}+{self.result_data.get('output_tokens',0)}"
            )

    def set_result(self, input_tokens: int = 0, output_tokens: int = 0, summary: str = ""):
        self.result_data = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "summary": summary,
        }


async def log_action(
    db_session_factory,
    document_id: str,
    action_type: str,
    provider: str,
    model: str,
    status: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration_ms: int = 0,
    error: str = "",
    summary: str = "",
):
    """Quick one-shot action logging without context manager."""
    log = AIActionLog(
        id=str(uuid.uuid4()),
        document_id=document_id,
        action_type=action_type,
        provider=provider,
        model=model,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        error_message=error[:500] if error else None,
        result_summary=summary[:300] if summary else None,
        created_at=_now(),
    )

    async with db_session_factory() as db:
        db.add(log)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
