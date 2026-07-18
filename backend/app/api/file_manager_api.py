"""File Manager API — scan, dedup, organize local files."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ScanRequest(BaseModel):
    path: str
    recursive: bool = True
    deep: bool = False  # compute full SHA-256 hashes for dedup


class OrganizeRequest(BaseModel):
    path: str
    target: str = ""
    strategy: str = "category"  # category | date | flat
    action: str = "copy"        # copy | move | symlink
    dry_run: bool = True


@router.post("/files/scan")
async def scan_files(req: ScanRequest):
    """Scan a directory and return file analysis."""
    from app.services.file_manager import scan_directory

    result = await scan_directory(
        root=req.path,
        recursive=req.recursive,
        deep=req.deep,
    )

    return {
        "path": req.path,
        "total_files": result.total_files,
        "total_size_mb": round(result.total_size / (1024 * 1024), 2),
        "duplicate_groups": len(result.duplicates),
        "duplicate_count": result.duplicate_count,
        "wasted_mb": round(result.wasted_bytes / (1024 * 1024), 2),
        "by_category": {
            cat: len(files) for cat, files in result.by_category.items()
        },
        "by_date": {
            date: len(files) for date, files in sorted(result.by_date.items())[-12:]
        },
        "sample_files": [
            {"name": f.name, "size_kb": round(f.size / 1024, 1),
             "category": f.category, "modified": f.modified[:10]}
            for f in result.files[:100]
        ],
        "duplicates": [
            {
                "hash": group[0].hash[:12],
                "count": len(group),
                "wasted_kb": round(sum(d.size for d in group[1:]) / 1024, 1),
                "files": [{"name": d.name, "path": d.path, "size_kb": round(d.size / 1024, 1)}
                          for d in group[:5]]
            }
            for group in result.duplicates[:20]
        ],
    }


@router.post("/files/organize")
async def organize_files(req: OrganizeRequest):
    """Organize files into folders by category or date."""
    from app.services.file_manager import organize_files

    plan = await organize_files(
        root=req.path,
        target=req.target,
        strategy=req.strategy,
        action=req.action,
        dry_run=req.dry_run,
    )

    return {
        "dry_run": req.dry_run,
        "action": req.action,
        "strategy": req.strategy,
        "files_to_organize": len(plan["files"]),
        "folders_to_create": len(plan["folders_created"]),
        "total_size_mb": round(plan["total_size"] / (1024 * 1024), 2),
        "folders": plan["folders_created"][:20],
        "sample": plan["files"][:50],
    }


@router.post("/files/dedup")
async def deduplicate_files(
    path: str = Query(...),
    dry_run: bool = Query(True),
):
    """Find and delete duplicate files. Keeps first copy."""
    from app.services.file_manager import delete_duplicates

    result = await delete_duplicates(root=path, dry_run=dry_run)

    return result
