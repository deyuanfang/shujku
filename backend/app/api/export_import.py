"""Data Export / Import API."""

import io
import json
import zipfile
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.database.connection import get_db
from app.database.models import Document, Category, Entity, Tag, DocumentTag, DocumentEntity, Relationship

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/export")
async def export_data(db: AsyncSession = Depends(get_db)):
    """Export all knowledge base data as a JSON file."""
    # Documents
    doc_result = await db.execute(select(Document).where(Document.is_active == 1))
    documents = []
    for doc in doc_result.scalars().all():
        documents.append({
            "id": doc.id, "title": doc.title, "content_type": doc.content_type,
            "source_url": doc.source_url, "raw_text": doc.raw_text,
            "word_count": doc.word_count, "char_count": doc.char_count,
            "importance": doc.importance,
            "created_at": doc.created_at, "updated_at": doc.updated_at,
        })

    # Categories
    cat_result = await db.execute(select(Category))
    categories = [
        {"id": c.id, "name": c.name, "parent_id": c.parent_id,
         "description": c.description, "color": c.color, "sort_order": c.sort_order}
        for c in cat_result.scalars().all()
    ]

    # Entities
    ent_result = await db.execute(select(Entity))
    entities = [
        {"id": e.id, "name": e.name, "type": e.type, "aliases": e.aliases,
         "description": e.description, "mention_count": e.mention_count}
        for e in ent_result.scalars().all()
    ]

    # Document-Entity links
    de_result = await db.execute(select(DocumentEntity))
    doc_entities = [
        {"document_id": de.document_id, "entity_id": de.entity_id, "relevance": de.relevance}
        for de in de_result.scalars().all()
    ]

    # Tags
    tag_result = await db.execute(select(Tag))
    tags = [{"id": t.id, "name": t.name, "color": t.color} for t in tag_result.scalars().all()]

    # Document-Tag links
    dt_result = await db.execute(select(DocumentTag))
    doc_tags = [
        {"document_id": dt.document_id, "tag_id": dt.tag_id, "confidence": dt.confidence}
        for dt in dt_result.scalars().all()
    ]

    # Relationships
    rel_result = await db.execute(select(Relationship))
    relationships = [
        {"id": r.id, "source_entity_id": r.source_entity_id,
         "target_entity_id": r.target_entity_id,
         "relation_type": r.relation_type, "description": r.description,
         "confidence": r.confidence}
        for r in rel_result.scalars().all()
    ]

    export_data = {
        "version": "0.2.0",
        "exported_at": _now(),
        "documents": documents,
        "categories": categories,
        "entities": entities,
        "document_entities": doc_entities,
        "tags": tags,
        "document_tags": doc_tags,
        "relationships": relationships,
    }

    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)

    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=personalkb-export-{_now()[:10]}.json"},
    )


@router.post("/import")
async def import_data(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Import knowledge base data from a JSON export file."""
    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "error", "message": "无效的导出文件格式"}

    imported = {"documents": 0, "categories": 0, "entities": 0, "tags": 0}

    # Import categories first
    cat_id_map = {}
    for cat_data in data.get("categories", []):
        result = await db.execute(select(Category).where(Category.name == cat_data["name"]))
        if result.scalar_one_or_none():
            continue
        old_id = cat_data["id"]
        new_id = str(uuid.uuid4())
        cat = Category(
            id=new_id, name=cat_data["name"],
            parent_id=cat_id_map.get(cat_data.get("parent_id", ""), cat_data.get("parent_id")),
            description=cat_data.get("description"), color=cat_data.get("color", "#6366f1"),
            sort_order=cat_data.get("sort_order", 0),
            created_at=_now(), updated_at=_now(),
        )
        db.add(cat)
        cat_id_map[old_id] = new_id
        imported["categories"] += 1

    await db.flush()

    # Import entities
    ent_id_map = {}
    for ent_data in data.get("entities", []):
        result = await db.execute(select(Entity).where(Entity.name == ent_data["name"]))
        if result.scalar_one_or_none():
            continue
        old_id = ent_data["id"]
        new_id = str(uuid.uuid4())
        entity = Entity(
            id=new_id, name=ent_data["name"], type=ent_data.get("type", "other"),
            aliases=ent_data.get("aliases"), description=ent_data.get("description"),
            mention_count=ent_data.get("mention_count", 1),
            created_at=_now(), updated_at=_now(),
        )
        db.add(entity)
        ent_id_map[old_id] = new_id
        imported["entities"] += 1

    await db.flush()

    # Import tags
    tag_id_map = {}
    for tag_data in data.get("tags", []):
        result = await db.execute(select(Tag).where(Tag.name == tag_data["name"]))
        if (existing := result.scalar_one_or_none()):
            tag_id_map[tag_data["id"]] = existing.id
            continue
        old_id = tag_data["id"]
        new_id = str(uuid.uuid4())
        tag = Tag(id=new_id, name=tag_data["name"], color=tag_data.get("color", "#a855f7"),
                  usage_count=0, created_at=_now())
        db.add(tag)
        tag_id_map[old_id] = new_id
        imported["tags"] += 1

    await db.flush()

    # Import documents
    doc_id_map = {}
    for doc_data in data.get("documents", []):
        new_id = str(uuid.uuid4())
        doc = Document(
            id=new_id, title=doc_data["title"],
            content_type=doc_data.get("content_type", "text"),
            source_url=doc_data.get("source_url"),
            original_hash=doc_data.get("id", new_id),  # Keep original ID as hash for dedup
            raw_text=doc_data.get("raw_text", ""),
            word_count=doc_data.get("word_count", 0),
            char_count=doc_data.get("char_count", 0),
            importance=doc_data.get("importance", 0.5),
            created_at=doc_data.get("created_at", _now()),
            updated_at=doc_data.get("updated_at", _now()),
            last_analyzed_at=_now(),
        )
        db.add(doc)
        doc_id_map[doc_data["id"]] = new_id
        imported["documents"] += 1

    await db.flush()

    # Restore document-entity links
    for de in data.get("document_entities", []):
        new_doc_id = doc_id_map.get(de["document_id"])
        new_ent_id = ent_id_map.get(de["entity_id"])
        if new_doc_id and new_ent_id:
            doc_entity = DocumentEntity(
                document_id=new_doc_id, entity_id=new_ent_id,
                relevance=de.get("relevance", 0.5), frequency=1,
            )
            db.add(doc_entity)

    # Restore document-tag links
    for dt in data.get("document_tags", []):
        new_doc_id = doc_id_map.get(dt["document_id"])
        new_tag_id = tag_id_map.get(dt["tag_id"])
        if new_doc_id and new_tag_id:
            doc_tag = DocumentTag(
                document_id=new_doc_id, tag_id=new_tag_id,
                confidence=dt.get("confidence", 1.0), is_auto=1, created_at=_now(),
            )
            db.add(doc_tag)

    # Restore entity relationships
    for rel in data.get("relationships", []):
        src_id = ent_id_map.get(rel["source_entity_id"])
        tgt_id = ent_id_map.get(rel["target_entity_id"])
        if src_id and tgt_id:
            relationship = Relationship(
                id=str(uuid.uuid4()),
                source_entity_id=src_id, target_entity_id=tgt_id,
                relation_type=rel.get("relation_type", "related_to"),
                description=rel.get("description"), confidence=rel.get("confidence", 0.5),
                source="import", created_at=_now(),
            )
            db.add(relationship)

    # Update category document counts
    for doc_id, doc in [(doc_id_map.get(d["id"]), d) for d in data.get("documents", [])]:
        if not doc_id:
            continue
        # Count will be updated on next scan

    return {"status": "ok", "imported": imported}
