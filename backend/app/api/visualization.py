"""Visualization API — provides data for tree and galaxy views."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.database.models import (
    Document, Category, Entity, Tag, KnowledgeNode, KnowledgeEdge,
    DocumentEntity,
)

router = APIRouter()


@router.get("/knowledge-tree")
async def get_knowledge_tree(db: AsyncSession = Depends(get_db)):
    """Build a knowledge-point tree from entities (or NLP keywords as fallback)."""
    import json

    # Get entities with documents
    ent_result = await db.execute(
        select(Entity, DocumentEntity, Document)
        .join(DocumentEntity, DocumentEntity.entity_id == Entity.id)
        .join(Document, Document.id == DocumentEntity.document_id)
        .where(Document.is_active == 1)
    )
    rows = ent_result.fetchall()

    # Build entity→docs map
    entity_docs: dict[str, dict] = {}
    doc_with_entities: set = set()
    for entity, de, doc in rows:
        doc_with_entities.add(doc.id)
        if entity.id not in entity_docs:
            entity_docs[entity.id] = {
                "id": entity.id, "label": entity.name, "type": "entity",
                "entity_type": entity.type, "color": _entity_color(entity.type),
                "children": [], "doc_count": 0,
            }
        entity_docs[entity.id]["children"].append({
            "id": doc.id, "label": doc.title, "type": "document",
            "content_type": doc.content_type, "importance": doc.importance,
            "word_count": doc.word_count,
        })
        entity_docs[entity.id]["doc_count"] += 1

    # Get all docs without entities — build keyword-based tree
    all_docs = (await db.execute(
        select(Document).where(Document.is_active == 1)
    )).scalars().all()

    # Also extract NLP keywords from documents as fallback branches
    keyword_docs: dict[str, dict] = {}
    for doc in all_docs:
        if doc.id in doc_with_entities:
            continue  # already covered by entities
        # Get keywords from document
        kws = []
        if doc.keywords:
            try: kws = json.loads(doc.keywords) if isinstance(doc.keywords, str) else doc.keywords
            except: pass
        if not kws and doc.raw_text:
            from app.services.nlp_pipeline import nlp_pipeline
            kws = nlp_pipeline.extract_keywords(doc.raw_text, top_n=5)
        for kw in kws[:3]:  # top 3 keywords per doc
            if kw not in keyword_docs:
                keyword_docs[kw] = {
                    "id": f"kw-{kw}", "label": kw, "type": "entity",
                    "entity_type": "concept", "color": "#8b5cf6",
                    "children": [], "doc_count": 0,
                }
            keyword_docs[kw]["children"].append({
                "id": doc.id, "label": doc.title, "type": "document",
                "content_type": doc.content_type, "importance": doc.importance,
                "word_count": doc.word_count,
            })
            keyword_docs[kw]["doc_count"] += 1

    # Merge entity and keyword trees
    all_entities = list(entity_docs.values()) + list(keyword_docs.values())
    sorted_entities = sorted(all_entities, key=lambda e: e["doc_count"], reverse=True)

    # Group by entity type
    type_groups: dict[str, dict] = {}
    for ent in sorted_entities:
        etype = ent.get("entity_type", "other")
        if etype not in type_groups:
            type_groups[etype] = {
                "id": f"type-{etype}", "label": _type_label(etype),
                "type": "category", "color": _entity_color(etype), "children": [],
            }
        type_groups[etype]["children"].append(ent)

    tree_children = list(type_groups.values())

    # Docs not in any branch
    all_doc_ids = doc_with_entities | {d.id for d in all_docs if any(
        d.id in kw_ch.get("children", []) for kw_ch in keyword_docs.values()
    )}
    uncategorized = [d for d in all_docs if d.id not in all_doc_ids]
    # Deduplicate
    seen_ids = set()
    uncat_unique = []
    for d in uncategorized:
        if d.id not in seen_ids:
            seen_ids.add(d.id)
            uncat_unique.append(d)

    if uncat_unique:
        tree_children.append({
            "id": "uncategorized-knowledge",
            "label": "其他知识点",
            "type": "category", "color": "#6b7280",
            "children": [
                {"id": d.id, "label": d.title, "type": "document",
                 "content_type": d.content_type, "importance": d.importance,
                 "word_count": d.word_count}
                for d in uncat_unique[:50]
            ],
        })

    return {"tree": {"id": "root", "label": "知识体系", "children": tree_children}}


def _entity_color(etype: str) -> str:
    colors = {
        "person": "#f59e0b", "organization": "#3b82f6", "location": "#10b981",
        "concept": "#8b5cf6", "event": "#ef4444", "technology": "#06b6d4",
    }
    return colors.get(etype, "#9ca3af")


def _type_label(etype: str) -> str:
    labels = {
        "person": "人物", "organization": "组织", "location": "地点",
        "concept": "概念", "event": "事件", "technology": "技术",
    }
    return labels.get(etype, etype)


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
