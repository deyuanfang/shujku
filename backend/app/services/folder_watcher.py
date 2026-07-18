"""Local Folder Watcher — auto-detects new files in watched directories and imports them."""

import os
import asyncio
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Track processed files to avoid re-importing
_processed_files: dict[str, float] = {}  # path -> mtime
_watch_tasks: dict[str, asyncio.Task] = {}
_running = False

WATCHED_DIRS: list[str] = []
SCAN_INTERVAL_SECONDS = 10


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _file_hash(path: str) -> str:
    """Quick hash of file path + size + mtime for dedup."""
    try:
        stat = os.stat(path)
        key = f"{path}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(key.encode()).hexdigest()
    except Exception:
        return ""


async def start_watcher(directories: list[str] | None = None):
    """Start the folder watcher background task."""
    global _running, WATCHED_DIRS

    if directories:
        WATCHED_DIRS = directories

    if _running:
        return

    _running = True
    logger.info(f"Folder watcher started. Watching: {WATCHED_DIRS}")

    # Start scanning loop
    asyncio.create_task(_scan_loop())


async def stop_watcher():
    """Stop the folder watcher."""
    global _running
    _running = False
    for path, task in _watch_tasks.items():
        task.cancel()
    _watch_tasks.clear()
    logger.info("Folder watcher stopped")


async def _scan_loop():
    """Background loop that periodically scans watched directories."""
    while _running:
        for directory in WATCHED_DIRS:
            if os.path.isdir(directory):
                await _scan_directory(directory)
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


async def _scan_directory(directory: str):
    """Scan a directory for new or modified files."""
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                file_path = entry.path
                file_hash = _file_hash(file_path)

                # Check if already processed
                if file_hash in _processed_files:
                    continue

                # Check if it's a supported type
                ext = Path(file_path).suffix.lower()
                from app.services.content_extractor import EXT_MAPPING
                if ext not in EXT_MAPPING:
                    continue

                logger.info(f"Watcher: new file detected: {file_path}")
                await _auto_import_file(file_path)
                _processed_files[file_hash] = time.time()

            elif entry.is_dir() and entry.name not in ('.git', '__pycache__', 'node_modules', '.venv', 'venv'):
                # Recurse into subdirectories
                await _scan_directory(entry.path)

    except PermissionError:
        pass
    except Exception as e:
        logger.error(f"Scan error in {directory}: {e}")


async def _auto_import_file(file_path: str):
    """Auto-import a detected file into the knowledge base."""
    import uuid
    from app.database.connection import async_session
    from app.database.models import Document, Category
    from app.services.content_extractor import extract_content, detect_content_type
    from app.services.nlp_pipeline import nlp_pipeline
    from app.utils.hash_utils import compute_file_hash
    from sqlalchemy import select

    try:
        path_obj = Path(file_path)
        content_type = detect_content_type(path_obj.name)
        file_hash = compute_file_hash(path_obj)

        async with async_session() as db:
            # Check duplicate
            result = await db.execute(
                select(Document).where(Document.original_hash == file_hash)
            )
            if result.scalar_one_or_none():
                logger.info(f"Watcher: skipping duplicate: {file_path}")
                return

            # Extract content
            extracted = await extract_content(
                content_type=content_type,
                file_path=path_obj,
            )

            # NLP classification
            cat_result = await db.execute(select(Category))
            categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
            classification = nlp_pipeline.classify(extracted["raw_text"], categories)

            # Create document
            doc = Document(
                id=str(uuid.uuid4()),
                title=extracted.get("title", path_obj.stem),
                content_type=content_type,
                source_path=file_path,
                original_hash=file_hash,
                raw_text=extracted["raw_text"],
                word_count=extracted.get("word_count", 0),
                char_count=extracted.get("char_count", 0),
                category_id=classification["category_id"],
                importance=0.5,
                is_active=1,
                created_at=_now(),
                updated_at=_now(),
                last_analyzed_at=_now(),
            )
            db.add(doc)

            # Update category count
            if classification["category_id"]:
                cat_r = await db.execute(
                    select(Category).where(Category.id == classification["category_id"])
                )
                if cat := cat_r.scalar_one_or_none():
                    cat.document_count += 1

            await db.commit()

            # Enqueue for AI analysis
            from app.services.task_queue import enqueue_analysis
            await enqueue_analysis(doc.id, doc.title, extracted["raw_text"])

            logger.info(
                f"Watcher: imported {file_path} → {doc.id[:8]} "
                f"({classification['category_name']}, {len(classification['keywords'])} keywords)"
            )

    except Exception as e:
        logger.error(f"Watcher: failed to import {file_path}: {e}")


import time  # for the hash dedup timestamp
