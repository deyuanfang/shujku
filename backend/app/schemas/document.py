from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentCreate(BaseModel):
    title: Optional[str] = None
    content_type: str  # text, markdown, pdf, image, url, note


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    category_id: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    content_type: str
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    original_hash: str
    word_count: int
    char_count: int
    category_id: Optional[str] = None
    importance: float
    created_at: str
    updated_at: str
    last_analyzed_at: Optional[str] = None


class DocumentDetailResponse(DocumentResponse):
    raw_text: Optional[str] = None
    summary: Optional[str] = None


class DocumentSearchResult(BaseModel):
    id: str
    title: str
    content_type: str
    snippet: str
    category_name: Optional[str] = None
    created_at: str
