"""Knowledge Graph Service — builds and maintains the graph from documents, entities, and relationships."""

import json
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database.models import (
    Document, Category, Entity, DocumentEntity,
    Relationship, KnowledgeNode, KnowledgeEdge,
    Tag, DocumentTag, Summary,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def update_knowledge_graph(
    db: AsyncSession,
    document: Document,
    llm_result: dict,
):
    """Update the knowledge graph with entities, relationships, tags from LLM analysis.

    This function:
    1. Creates/merges entities from LLM extraction
    2. Links entities to the document
    3. Creates relationships between entities
    4. Creates tags from LLM suggestions
    5. Updates knowledge_nodes and knowledge_edges materialized views
    """

    # ── 1. Entity Resolution ──────────────────────
    entities_raw = llm_result.get("entities", [])
    created_entities = []

    for ent_data in entities_raw:
        entity = await _resolve_entity(db, ent_data)
        created_entities.append(entity)

        # Link entity to document
        doc_entity = DocumentEntity(
            document_id=document.id,
            entity_id=entity.id,
            relevance=0.7,  # LLM-extracted entities are highly relevant
            frequency=1,
        )
        db.add(doc_entity)

    # Update entity mention counts
    for entity in created_entities:
        entity.mention_count += 1

    # Entities already linked via DocumentEntity table above
    # ── 2. Create Relationships ───────────────────
    relationships_raw = llm_result.get("relationships", [])
    entity_name_to_id = {e.name: e.id for e in created_entities}
    # Also look up existing entities by name
    for ent_data in entities_raw:
        name = ent_data.get("name", "")
        if name not in entity_name_to_id:
            result = await db.execute(
                select(Entity).where(Entity.name == name)
            )
            existing = result.scalar_one_or_none()
            if existing:
                entity_name_to_id[name] = existing.id

    for rel_data in relationships_raw:
        source_name = rel_data.get("source", "")
        target_name = rel_data.get("target", "")
        source_id = entity_name_to_id.get(source_name)
        target_id = entity_name_to_id.get(target_name)

        if source_id and target_id and source_id != target_id:
            # Check for existing relationship
            result = await db.execute(
                select(Relationship).where(
                    Relationship.source_entity_id == source_id,
                    Relationship.target_entity_id == target_id,
                    Relationship.relation_type == rel_data.get("relation_type", "related_to"),
                )
            )
            if not result.scalar_one_or_none():
                rel = Relationship(
                    id=str(uuid.uuid4()),
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relation_type=rel_data.get("relation_type", "related_to"),
                    description=rel_data.get("description", ""),
                    confidence=0.7,
                    evidence_doc_id=document.id,
                    source="llm",
                    created_at=_now(),
                )
                db.add(rel)

    # ── 4. Create Tags ────────────────────────────
    suggested_tags = llm_result.get("suggested_tags", [])
    for tag_name in suggested_tags:
        if not tag_name or len(tag_name) > 20:
            continue
        # Find or create tag
        result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(
                id=str(uuid.uuid4()),
                name=tag_name,
                usage_count=0,
                created_at=_now(),
            )
            db.add(tag)
            await db.flush()

        tag.usage_count += 1

        # Link document to tag
        doc_tag = DocumentTag(
            document_id=document.id,
            tag_id=tag.id,
            confidence=0.8,
            is_auto=1,
            created_at=_now(),
        )
        db.add(doc_tag)

    # ── 5. Materialize Knowledge Graph Nodes/Edges ─

    # Document node
    await _upsert_node(
        db,
        node_type="document",
        ref_id=document.id,
        label=document.title,
        importance=document.importance,
        color=None,
    )

    # Category node (if assigned)
    if document.category_id:
        cat_result = await db.execute(
            select(Category).where(Category.id == document.category_id)
        )
        category = cat_result.scalar_one_or_none()
        if category:
            await _upsert_node(
                db,
                node_type="category",
                ref_id=category.id,
                label=category.name,
                importance=0.8,
                color=category.color,
            )
            # Edge: document belongs to category
            await _upsert_edge(
                db,
                source_ref_id=document.id,
                source_type="document",
                target_ref_id=category.id,
                target_type="category",
                edge_type="belongs_to",
                weight=0.9,
            )

    # Entity nodes and edges
    for entity in created_entities:
        await _upsert_node(
            db,
            node_type="entity",
            ref_id=entity.id,
            label=entity.name,
            importance=min(1.0, entity.mention_count / 20),
            color=_entity_color(entity.type),
            metadata={"entity_type": entity.type},
        )
        # Edge: document references entity
        await _upsert_edge(
            db,
            source_ref_id=document.id,
            source_type="document",
            target_ref_id=entity.id,
            target_type="entity",
            edge_type="references",
            weight=0.6,
        )

    # Entity-to-entity edges from relationships
    for rel_data in relationships_raw:
        source_name = rel_data.get("source", "")
        target_name = rel_data.get("target", "")
        source_id = entity_name_to_id.get(source_name)
        target_id = entity_name_to_id.get(target_name)
        if source_id and target_id:
            await _upsert_edge(
                db,
                source_ref_id=source_id,
                source_type="entity",
                target_ref_id=target_id,
                target_type="entity",
                edge_type="related_to",
                weight=0.5,
                label=rel_data.get("relation_type", ""),
            )


async def _resolve_entity(db: AsyncSession, ent_data: dict) -> Entity:
    """Find existing entity by name/alias or create a new one."""
    name = ent_data.get("name", "").strip()
    if not name:
        return None

    # Try exact name match
    result = await db.execute(select(Entity).where(Entity.name == name))
    entity = result.scalar_one_or_none()
    if entity:
        # Update description if we have new info
        if ent_data.get("description") and not entity.description:
            entity.description = ent_data["description"]
        entity.updated_at = _now()
        return entity

    # Try alias match
    result = await db.execute(select(Entity))
    all_entities = result.scalars().all()
    for existing in all_entities:
        if existing.aliases:
            try:
                aliases = json.loads(existing.aliases)
                if name in aliases:
                    return existing
            except (json.JSONDecodeError, TypeError):
                pass

    # Create new entity
    entity = Entity(
        id=str(uuid.uuid4()),
        name=name,
        type=ent_data.get("type", "other"),
        description=ent_data.get("description", ""),
        mention_count=0,
        source="llm",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(entity)
    await db.flush()
    return entity


async def _upsert_node(
    db: AsyncSession,
    node_type: str,
    ref_id: str,
    label: str,
    importance: float = 0.5,
    color: str | None = None,
    metadata: dict | None = None,
):
    """Create or update a knowledge graph node."""
    result = await db.execute(
        select(KnowledgeNode).where(
            KnowledgeNode.node_type == node_type,
            KnowledgeNode.ref_id == ref_id,
        )
    )
    node = result.scalar_one_or_none()

    if node:
        node.label = label
        node.importance = importance
        if color:
            node.color = color
        node.updated_at = _now()
    else:
        node = KnowledgeNode(
            id=str(uuid.uuid4()),
            node_type=node_type,
            ref_id=ref_id,
            label=label,
            importance=importance,
            radius=_default_radius(node_type, importance),
            color=color,
            metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
            updated_at=_now(),
        )
        db.add(node)


async def _upsert_edge(
    db: AsyncSession,
    source_ref_id: str,
    source_type: str,
    target_ref_id: str,
    target_type: str,
    edge_type: str,
    weight: float = 0.5,
    label: str = "",
):
    """Create a knowledge graph edge (deduplicated)."""
    # Find source node
    src_result = await db.execute(
        select(KnowledgeNode).where(
            KnowledgeNode.node_type == source_type,
            KnowledgeNode.ref_id == source_ref_id,
        )
    )
    src_node = src_result.scalar_one_or_none()

    # Find target node
    tgt_result = await db.execute(
        select(KnowledgeNode).where(
            KnowledgeNode.node_type == target_type,
            KnowledgeNode.ref_id == target_ref_id,
        )
    )
    tgt_node = tgt_result.scalar_one_or_none()

    if not src_node or not tgt_node:
        return

    # Check for existing edge
    result = await db.execute(
        select(KnowledgeEdge).where(
            KnowledgeEdge.source_node_id == src_node.id,
            KnowledgeEdge.target_node_id == tgt_node.id,
            KnowledgeEdge.edge_type == edge_type,
        )
    )
    if result.scalar_one_or_none():
        return

    edge = KnowledgeEdge(
        id=str(uuid.uuid4()),
        source_node_id=src_node.id,
        target_node_id=tgt_node.id,
        edge_type=edge_type,
        weight=weight,
        label=label,
    )
    db.add(edge)


def _entity_color(entity_type: str) -> str:
    colors = {
        "person": "#f59e0b",
        "organization": "#3b82f6",
        "location": "#10b981",
        "concept": "#8b5cf6",
        "event": "#ef4444",
        "technology": "#06b6d4",
        "other": "#9ca3af",
    }
    return colors.get(entity_type, "#9ca3af")


def _default_radius(node_type: str, importance: float) -> float:
    if node_type == "category":
        return 25 + importance * 10
    elif node_type == "document":
        return 10 + importance * 15
    elif node_type == "entity":
        return 5 + importance * 10
    return 10
