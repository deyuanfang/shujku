from sqlalchemy import (
    Column, String, Integer, Float, Text, ForeignKey, Index, UniqueConstraint, event,
)
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid


def gen_uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ============================================================
# DOCUMENTS
# ============================================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    content_type = Column(String, nullable=False)  # text, markdown, pdf, image, url, note
    source_path = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    original_hash = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    lang = Column(String, default="zh")
    category_id = Column(String, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    secondary_categories = Column(Text, nullable=True)  # JSON array of category IDs
    summary = Column(Text, nullable=True)         # AI-generated summary
    keywords = Column(Text, nullable=True)         # JSON array of keywords
    importance = Column(Float, default=0.5)
    is_active = Column(Integer, default=1)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    last_analyzed_at = Column(String, nullable=True)

    # Relationships
    category = relationship("Category", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    tags = relationship("DocumentTag", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("DocumentEntity", back_populates="document", cascade="all, delete-orphan")
    change_logs = relationship("ChangeLog", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_category", "category_id"),
        Index("idx_documents_content_type", "content_type"),
        Index("idx_documents_hash", "original_hash"),
        Index("idx_documents_created", "created_at"),
    )


# ============================================================
# DOCUMENT VERSIONS
# ============================================================

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    source_hash = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    created_at = Column(String, nullable=False)

    document = relationship("Document", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version_number"),
        Index("idx_versions_document", "document_id"),
    )


# ============================================================
# CATEGORIES
# ============================================================

class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    description = Column(Text, nullable=True)
    color = Column(String, default="#6366f1")
    icon = Column(String, default="folder")
    sort_order = Column(Integer, default=0)
    document_count = Column(Integer, default=0)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    documents = relationship("Document", back_populates="category")
    parent = relationship("Category", back_populates="children", remote_side=[id])
    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_categories_parent", "parent_id"),
    )


# ============================================================
# TAGS
# ============================================================

class Tag(Base):
    __tablename__ = "tags"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, unique=True)
    color = Column(String, default="#a855f7")
    usage_count = Column(Integer, default=0)
    created_at = Column(String, nullable=False)

    document_tags = relationship("DocumentTag", back_populates="tag", cascade="all, delete-orphan")


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(String, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    confidence = Column(Float, default=1.0)
    is_auto = Column(Integer, default=0)
    created_at = Column(String, nullable=False)

    document = relationship("Document", back_populates="tags")
    tag = relationship("Tag", back_populates="document_tags")


# ============================================================
# ENTITIES
# ============================================================

class Entity(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # person, organization, location, concept, event, technology, other
    aliases = Column(Text, nullable=True)  # JSON array
    description = Column(Text, nullable=True)
    mention_count = Column(Integer, default=1)
    source = Column(String, default="nlp")
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    document_entities = relationship("DocumentEntity", back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_entities_type", "type"),
        Index("idx_entities_name", "name"),
    )


class DocumentEntity(Base):
    __tablename__ = "document_entities"

    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    relevance = Column(Float, default=0.5)
    frequency = Column(Integer, default=1)

    document = relationship("Document", back_populates="entities")
    entity = relationship("Entity", back_populates="document_entities")


# ============================================================
# RELATIONSHIPS
# ============================================================

class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(String, primary_key=True, default=gen_uuid)
    source_entity_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id = Column(String, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    confidence = Column(Float, default=0.5)
    evidence_doc_id = Column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    source = Column(String, default="llm")
    created_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_relationships_source", "source_entity_id"),
        Index("idx_relationships_target", "target_entity_id"),
    )


# ============================================================
# KNOWLEDGE GRAPH (materialized view for visualization)
# ============================================================

class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id = Column(String, primary_key=True, default=gen_uuid)
    node_type = Column(String, nullable=False)  # document, category, entity, tag
    ref_id = Column(String, nullable=False)
    label = Column(String, nullable=False)
    importance = Column(Float, default=0.5)
    x = Column(Float, nullable=True)
    y = Column(Float, nullable=True)
    radius = Column(Float, default=10)
    color = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("node_type", "ref_id"),
    )


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id = Column(String, primary_key=True, default=gen_uuid)
    source_node_id = Column(String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False)
    edge_type = Column(String, nullable=False)  # contains, references, related_to, belongs_to
    weight = Column(Float, default=0.5)
    label = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", "edge_type"),
    )


# ============================================================
# SUMMARIES
# ============================================================

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=gen_uuid)
    target_type = Column(String, nullable=False)  # document, category
    target_id = Column(String, nullable=False)
    summary_text = Column(Text, nullable=False)
    key_points = Column(Text, nullable=True)  # JSON array
    model = Column(String, default="claude")
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    created_at = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("target_type", "target_id"),
    )


# ============================================================
# CHANGE LOGS
# ============================================================

class ChangeLog(Base):
    __tablename__ = "change_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    old_version_id = Column(String, ForeignKey("document_versions.id"), nullable=False)
    new_version_id = Column(String, ForeignKey("document_versions.id"), nullable=False)
    severity = Column(Float, nullable=False)
    severity_label = Column(String, nullable=False)  # minor, moderate, significant, major
    content_diff = Column(Text, nullable=True)
    entity_changes = Column(Text, nullable=True)  # JSON
    is_confirmed = Column(Integer, default=0)
    confirmed_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    document = relationship("Document", back_populates="change_logs")

    __table_args__ = (
        Index("idx_changelogs_document", "document_id"),
        Index("idx_changelogs_unconfirmed", "is_confirmed"),
    )


# ============================================================
# ALERTS / NOTIFICATIONS
# ============================================================

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    alert_type = Column(String, nullable=False)  # change, conflict, review, system
    related_item_id = Column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    severity = Column(String, default="medium")
    is_read = Column(Integer, default=0)
    created_at = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_alerts_unread", "is_read"),
    )


# ============================================================
# SETTINGS
# ============================================================

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(String, nullable=False)


# ============================================================
# FTS5 Virtual Table Setup
# ============================================================

# FTS5 setup is done via raw SQL since SQLAlchemy doesn't natively support virtual tables.
# The SQL will be executed in init_db() or via Alembic migration.

FTS5_SETUP_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    raw_text,
    content='documents',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS documents_fts_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, raw_text)
    VALUES (new.rowid, new.title, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS documents_fts_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, raw_text)
    VALUES ('delete', old.rowid, old.title, old.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS documents_fts_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, raw_text)
    VALUES ('delete', old.rowid, old.title, old.raw_text);
    INSERT INTO documents_fts(rowid, title, raw_text)
    VALUES (new.rowid, new.title, new.raw_text);
END;
"""
