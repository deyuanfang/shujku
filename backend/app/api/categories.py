"""Categories API."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.connection import get_db
from app.database.models import Category, Document

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


CATEGORY_COLORS = [
    "#6366f1", "#ec4899", "#f59e0b", "#10b981",
    "#3b82f6", "#8b5cf6", "#ef4444", "#06b6d4",
    "#84cc16", "#f97316",
]


@router.get("")
async def list_categories(
    tree: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """List all categories, optionally as a tree."""
    result = await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )
    categories = result.scalars().all()

    cat_list = [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "description": c.description,
            "color": c.color,
            "icon": c.icon,
            "document_count": c.document_count,
            "created_at": c.created_at,
        }
        for c in categories
    ]

    if tree:
        return _build_tree(cat_list)
    return cat_list


def _build_tree(items: list[dict]) -> list[dict]:
    """Build a nested tree structure from flat category list."""
    by_id = {item["id"]: {**item, "children": []} for item in items}
    roots = []

    for item_id, node in by_id.items():
        parent_id = node["parent_id"]
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


@router.post("")
async def create_category(
    name: str = Query(...),
    parent_id: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Create a new category."""
    # Assign a color
    result = await db.execute(select(func.count()).select_from(Category))
    count = result.scalar() or 0
    color = CATEGORY_COLORS[count % len(CATEGORY_COLORS)]

    cat = Category(
        id=str(uuid.uuid4()),
        name=name,
        parent_id=parent_id,
        description=description,
        color=color,
        sort_order=count,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(cat)
    await db.flush()

    return {
        "id": cat.id,
        "name": cat.name,
        "parent_id": cat.parent_id,
        "color": cat.color,
    }


@router.put("/{cat_id}")
async def update_category(
    cat_id: str,
    name: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Update a category."""
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")

    if name is not None:
        cat.name = name
    if parent_id is not None:
        cat.parent_id = parent_id
    if color is not None:
        cat.color = color
    cat.updated_at = _now()

    return {"status": "ok", "id": cat.id}


@router.delete("/{cat_id}")
async def delete_category(
    cat_id: str,
    reassign_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Delete a category, optionally reassigning its documents."""
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")

    # Reassign documents
    if reassign_to:
        docs_result = await db.execute(
            select(Document).where(Document.category_id == cat_id)
        )
        docs = docs_result.scalars().all()
        for doc in docs:
            doc.category_id = reassign_to
    else:
        # Move documents to uncategorized
        docs_result = await db.execute(
            select(Document).where(Document.category_id == cat_id)
        )
        docs = docs_result.scalars().all()
        for doc in docs:
            doc.category_id = None

    await db.delete(cat)
    return {"status": "ok", "message": f"分类 '{cat.name}' 已删除"}

