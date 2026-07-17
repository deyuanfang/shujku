"""Visualization API — provides data for tree and galaxy views."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.database.models import (
    Document, Category, Entity, Tag, KnowledgeNode, KnowledgeEdge,
)

router = APIRouter()


@router.get("/tree")
async def get_tree_data(db: AsyncSession = Depends(get_db)):
    """Return hierarchical tree data for D3 tree visualization."""
    # Get categories with counts
    cat_result = await db.execute(
        select(Category).order_by(Category.sort_order)
    )
    categories = cat_result.scalars().all()

    # Get documents grouped by category
    doc_result = await db.execute(
        select(Document)
        .where(Document.is_active == 1)
        .order_by(Document.updated_at.desc())
    )
    documents = doc_result.scalars().all()

    # Build category lookup
    doc_by_cat: dict[str, list] = {}
    uncategorized = []

    for doc in documents:
        if doc.category_id:
            doc_by_cat.setdefault(doc.category_id, []).append(doc)
        else:
            uncategorized.append(doc)

    # Build tree
    def build_category_node(cat: Category) -> dict:
        children = []
        for doc in doc_by_cat.get(cat.id, []):
            children.append({
                "id": doc.id,
                "label": doc.title,
                "type": "document",
                "content_type": doc.content_type,
                "importance": doc.importance,
                "word_count": doc.word_count,
            })

        # Recursively add subcategories
        for sub in categories:
            if sub.parent_id == cat.id:
                children.append(build_category_node(sub))

        return {
            "id": cat.id,
            "label": cat.name,
            "type": "category",
            "color": cat.color,
            "count": cat.document_count,
            "children": children,
        }

    # Root categories (no parent)
    roots = []
    for cat in categories:
        if not cat.parent_id:
            roots.append(build_category_node(cat))

    # Add uncategorized documents
    if uncategorized:
        uncat_children = [
            {
                "id": doc.id,
                "label": doc.title,
                "type": "document",
                "content_type": doc.content_type,
                "importance": doc.importance,
                "word_count": doc.word_count,
            }
            for doc in uncategorized
        ]
        roots.append({
            "id": "uncategorized",
            "label": "未分类",
            "type": "category",
            "color": "#9ca3af",
            "count": len(uncategorized),
            "children": uncat_children,
        })

    return {
        "tree": {
            "id": "root",
            "label": "知识库",
            "children": roots,
        }
    }


@router.get("/galaxy")
async def get_galaxy_data(
    db: AsyncSession = Depends(get_db),
):
    """Return flat nodes + edges data for D3 force-directed galaxy visualization."""
    nodes = []
    edges = []

    # Add categories as "stars"
    cat_result = await db.execute(select(Category))
    categories = cat_result.scalars().all()

    for cat in categories:
        node_id = f"cat-{cat.id}"
        nodes.append({
            "id": node_id,
            "refId": cat.id,
            "label": cat.name,
            "type": "category",
            "importance": 0.8,
            "radius": 25 + cat.document_count * 2,
            "color": cat.color,
            "clusterId": cat.id,
        })

    # Add documents as "planets"
    doc_result = await db.execute(
        select(Document).where(Document.is_active == 1)
    )
    documents = doc_result.scalars().all()

    for doc in documents:
        node_id = f"doc-{doc.id}"
        nodes.append({
            "id": node_id,
            "refId": doc.id,
            "label": doc.title,
            "type": "document",
            "contentType": doc.content_type,
            "importance": doc.importance,
            "radius": 10 + doc.importance * 20,
            "color": None,  # Will inherit category color
            "clusterId": doc.category_id or "uncategorized",
        })

        # Edge: document belongs to category
        if doc.category_id:
            edges.append({
                "source": node_id,
                "target": f"cat-{doc.category_id}",
                "type": "belongs_to",
                "weight": 0.9,
            })

    # Add entities as "moons"
    ent_result = await db.execute(
        select(Entity).order_by(Entity.mention_count.desc()).limit(100)
    )
    entities = ent_result.scalars().all()

    ENTITY_COLORS = {
        "person": "#f59e0b",
        "organization": "#3b82f6",
        "location": "#10b981",
        "concept": "#8b5cf6",
        "event": "#ef4444",
        "technology": "#06b6d4",
        "other": "#9ca3af",
    }

    for ent in entities:
        node_id = f"ent-{ent.id}"
        nodes.append({
            "id": node_id,
            "refId": ent.id,
            "label": ent.name,
            "type": "entity",
            "entityType": ent.type,
            "importance": min(1.0, ent.mention_count / 50),
            "radius": 5 + min(20, ent.mention_count * 2),
            "color": ENTITY_COLORS.get(ent.type, "#9ca3af"),
            "clusterId": None,
        })

    return {
        "galaxy": {
            "nodes": nodes,
            "edges": edges,
        }
    }


@router.get("/stats")
async def get_visualization_stats(db: AsyncSession = Depends(get_db)):
    """Return stats for the dashboard view."""
    # Same as /stats but focused on visualization needs
    doc_count_result = await db.execute(
        select(Document).where(Document.is_active == 1)
    )
    docs = doc_count_result.scalars().all()

    cat_result = await db.execute(select(Category))
    cats = cat_result.scalars().all()

    return {
        "document_count": len(docs),
        "category_count": len(cats),
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "color": c.color,
                "count": c.document_count,
            }
            for c in cats
        ],
    }
