"""Storage API — manage local/NAS/removable/cloud storage backends."""

import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database.connection import get_db
from app.services.storage import StorageType, StorageStatus
from app.services.storage.local import LocalStorage
from app.services.storage.nas import NASStorage
from app.services.storage.removable import RemovableStorage

router = APIRouter()

# Active storage backends registry
_storage_backends: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ── List available storage ─────────────────────────

@router.get("/list")
async def list_storage():
    """List all configured storage backends and auto-detect available ones."""
    result = []

    # 1. Local storage (always available)
    local = LocalStorage()
    await local.connect({"root_path": ".", "name": "本地存储"})
    info = await local.get_info()
    result.append({
        "id": "local", "name": "本地存储", "type": "local",
        "status": "online", "icon": "hard-drive",
        "description": "本地文件系统",
        "info": {"free_gb": info.free_size_gb, "total_gb": info.total_size_gb},
    })

    # 2. NAS — skip auto-detection (can be slow), require manual config
    result.append({
        "id": "nas", "name": "网络存储 (NAS)", "type": "nas",
        "status": "available", "icon": "server",
        "description": "输入网络共享路径后扫描 (如 \\\\192.168.1.100\\share)",
    })

    # 3. Removable — skip auto-detection, require manual config
    result.append({
        "id": "removable", "name": "移动存储", "type": "removable",
        "status": "available", "icon": "usb",
        "description": "输入移动存储路径后扫描 (如 D:\\)",
    })

    # 4. Cloud storage (configured)
    result.append({
        "id": "baidu", "name": "百度网盘", "type": "baidu_cloud",
        "status": "configured" if False else "not_configured", "icon": "cloud",
        "description": "需要配置 API Key 后使用",
    })

    return result


# ── Scan storage ───────────────────────────────────

class ScanRequest(BaseModel):
    storage_id: str
    root_path: str = ""
    recursive: bool = True
    file_types: Optional[list[str]] = None  # e.g. ['.md', '.pdf']


@router.post("/scan")
async def scan_storage(req: ScanRequest):
    """Scan a storage backend for supported files."""
    backend = await _get_backend(req.storage_id, req.root_path)
    if not backend:
        raise HTTPException(404, "存储不可用")

    files = await backend.scan(
        root_path=req.root_path,
        recursive=req.recursive,
        file_types=req.file_types,
    )

    return {
        "storage_id": req.storage_id,
        "total": len(files),
        "files": [
            {
                "path": f.path, "name": f.name,
                "size_bytes": f.size_bytes, "size_mb": round(f.size_bytes / (1024**2), 2),
                "modified_at": f.modified_at, "content_type": f.content_type,
            }
            for f in files[:500]  # Limit to 500 results
        ],
    }


# ── Import from storage ────────────────────────────

@router.post("/import")
async def import_from_storage(
    storage_id: str = Query(...),
    file_paths: str = Query(...),  # Comma-separated relative paths
    db: AsyncSession = Depends(get_db),
):
    """Import selected files from storage into the knowledge base."""
    from app.services.content_extractor import extract_content, detect_content_type
    from app.utils.hash_utils import compute_text_hash, compute_file_hash
    from app.database.models import Document, Category
    from sqlalchemy import select
    import tempfile, os

    backend = await _get_backend(storage_id)
    if not backend:
        raise HTTPException(404, "存储不可用")

    paths = [p.strip() for p in file_paths.split(",") if p.strip()]
    imported = []
    errors = []

    for path in paths:
        try:
            content_bytes = await backend.read_file(path)
            content_type = detect_content_type(path)

            # Save to temp file for parsing
            suffix = os.path.splitext(path)[1] or ".tmp"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(content_bytes)
            tmp.close()

            file_path_obj = __import__('pathlib').Path(tmp.name)
            file_hash = compute_text_hash(content_bytes.decode("utf-8", errors="replace"))

            # Check duplicate
            result = await db.execute(
                select(Document).where(Document.original_hash == file_hash)
            )
            if result.scalar_one_or_none():
                imported.append({"path": path, "status": "duplicate"})
                os.unlink(tmp.name)
                continue

            # Extract content
            extracted = await extract_content(
                content_type=content_type,
                file_path=file_path_obj,
            )

            # NLP classification
            from app.services.nlp_pipeline import nlp_pipeline
            cat_result = await db.execute(select(Category))
            categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
            classification = nlp_pipeline.classify(extracted["raw_text"], categories)

            doc = Document(
                id=str(uuid.uuid4()),
                title=extracted["title"],
                content_type=content_type,
                source_path=f"{storage_id}:{path}",
                original_hash=file_hash,
                raw_text=extracted["raw_text"],
                word_count=extracted.get("word_count", 0),
                char_count=extracted.get("char_count", 0),
                category_id=classification["category_id"],
                created_at=_now(), updated_at=_now(), last_analyzed_at=_now(),
            )
            db.add(doc)

            # Update category count
            if classification["category_id"]:
                cat_result2 = await db.execute(
                    select(Category).where(Category.id == classification["category_id"])
                )
                if cat := cat_result2.scalar_one_or_none():
                    cat.document_count += 1

            imported.append({
                "path": path, "status": "ok",
                "document_id": doc.id, "title": doc.title,
                "category": classification["category_name"],
                "keywords": classification["keywords"],
            })
            os.unlink(tmp.name)

        except Exception as e:
            errors.append({"path": path, "error": str(e)})

    await db.flush()

    # Enqueue for async analysis
    for item in imported:
        if item["status"] == "ok":
            from app.services.task_queue import enqueue_analysis
            await enqueue_analysis(
                item["document_id"], item["title"],
                "",  # Content will be read from DB
            )

    return {"imported": len([i for i in imported if i["status"] == "ok"]),
            "duplicates": len([i for i in imported if i["status"] == "duplicate"]),
            "errors": len(errors), "items": imported}


# ── Cloud OAuth ────────────────────────────────────

@router.get("/cloud/auth-url")
async def get_cloud_auth_url(cloud_type: str = Query("baidu")):
    """Get OAuth authorization URL for cloud storage."""
    from app.services.storage.cloud.baidu_cloud import BaiduCloudConnector
    from app.config import settings

    if cloud_type == "baidu":
        connector = BaiduCloudConnector(
            app_key=settings.llm_api_key or "",  # Reuse API key field for Baidu app key
            redirect_uri="http://localhost:8765/api/v1/storage/cloud/callback",
        )
        url = await connector.get_auth_url()
        return {"auth_url": url}
    return {"error": "Unsupported cloud type"}


@router.get("/cloud/callback")
async def cloud_oauth_callback(code: str = Query(...), state: str = Query("")):
    """Handle OAuth callback from cloud storage provider."""
    from app.services.storage.cloud.baidu_cloud import BaiduCloudConnector

    connector = BaiduCloudConnector()
    ok = await connector.handle_callback(code)
    if ok:
        info = await connector.get_info()
        _storage_backends["baidu"] = {"backend": connector, "info": info}
        return {"status": "connected", "name": info.name}
    return {"status": "failed", "error": "OAuth authorization failed"}


# ── Helper ─────────────────────────────────────────

async def _get_backend(storage_id: str, root_path: str = ""):
    """Get a storage backend instance by ID. root_path required for NAS/removable."""
    if storage_id == "local":
        backend = LocalStorage()
        await backend.connect({"root_path": ".", "name": "本地存储"})
        return backend

    cached = _storage_backends.get(storage_id)
    if cached and cached["backend"]:
        return cached["backend"]

    if storage_id == "nas" and root_path:
        backend = NASStorage()
        if await backend.connect({"root_path": root_path, "name": "NAS存储"}):
            _storage_backends["nas"] = {"backend": backend}
            return backend

    if storage_id == "removable" and root_path:
        backend = RemovableStorage()
        if await backend.connect({"root_path": root_path, "name": "移动存储"}):
            _storage_backends["removable"] = {"backend": backend}
            return backend

    return None
