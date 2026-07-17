# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PersonalKB — 个人知识库管理桌面应用 (Personal Knowledge Base Manager).
Electron + React (TypeScript) frontend with a Python (FastAPI) backend, SQLite storage, and hybrid AI (local NLP + Claude API).

## Architecture

```
Electron (desktop shell)
  ├── spawns Python subprocess (FastAPI on localhost:8765)
  └── loads React SPA (Vite dev server or built files)

React (frontend) ──HTTP──► FastAPI (backend) ──SQL──► SQLite
                               │
                               ├── jieba + TF-IDF (local NLP, sync)
                               └── Claude API (deep analysis, async)
```

## Common Commands

### Backend
```bash
cd backend
pip install -r requirements.txt        # Install all dependencies
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload  # Dev server
```

### Frontend
```bash
cd frontend
npm install                            # Install dependencies
npm run dev                            # Vite dev server on :5173
npm run build                          # Production build
```

### Electron (full desktop app)
```bash
cd frontend
npm run electron:dev                   # Electron dev mode
npm run electron:build                 # Package desktop app
```

## Key Files

### Backend Core
- `backend/app/main.py` — FastAPI app factory with CORS, lifespan, health endpoint
- `backend/app/config.py` — Pydantic settings (DB URL, LLM key, upload path)
- `backend/app/database/models.py` — All SQLAlchemy ORM models (Document, Category, Entity, KnowledgeNode, etc.)
- `backend/app/database/connection.py` — Async SQLAlchemy engine + session factory

### Backend Services
- `backend/app/services/nlp_pipeline.py` — Chinese NLP: jieba segmentation → TF-IDF classification → keyword extraction
- `backend/app/services/content_extractor.py` — Routes content to correct parser based on type
- `backend/app/services/file_handler.py` — Content-addressed file storage (SHA-256 based)
- `backend/app/services/parsers/text_parser.py` — Text/Markdown files
- `backend/app/services/parsers/pdf_parser.py` — PDF via PyMuPDF
- `backend/app/services/parsers/image_parser.py` — OCR via PaddleOCR
- `backend/app/services/parsers/web_scraper.py` — Web page scraping via httpx + BeautifulSoup

### Backend API Routes
- `backend/app/api/router.py` — Aggregated router (prefix: /api/v1)
- `backend/app/api/upload.py` — POST /upload/file, /upload/url, /upload/note
- `backend/app/api/documents.py` — GET/PUT/DELETE /documents
- `backend/app/api/categories.py` — CRUD /categories with tree support
- `backend/app/api/search.py` — FTS5 full-text search
- `backend/app/api/visualization.py` — GET /visualization/tree, /visualization/galaxy
- `backend/app/api/changes.py` — Change logs + alerts API
- `backend/app/api/stats.py` — Dashboard statistics

### Frontend Core
- `frontend/src/App.tsx` — Router setup with 6 routes
- `frontend/src/store/index.ts` — Zustand stores (document, category, UI, notification, stats)
- `frontend/src/services/api.ts` — Axios-based API client matching all backend endpoints
- `frontend/src/types/index.ts` — TypeScript interfaces for all data types

### Frontend Pages
- `frontend/src/pages/DashboardPage.tsx` — Stats cards, recent docs, top categories
- `frontend/src/pages/DocumentsPage.tsx` — Document list with grid/list view + type filter
- `frontend/src/pages/DocumentDetailPage.tsx` — Document viewer with preview/raw tabs
- `frontend/src/pages/KnowledgeGraphPage.tsx` — D3.js tree view + D3 force galaxy view
- `frontend/src/pages/SearchPage.tsx` — Full-text search with snippet display
- `frontend/src/pages/SettingsPage.tsx` — LLM config, storage, appearance settings

### Frontend Layout
- `frontend/src/components/layout/AppShell.tsx` — Main layout with sidebar + header + content
- `frontend/src/components/layout/Sidebar.tsx` — Navigation + category tree
- `frontend/src/components/layout/Header.tsx` — Search bar + notification bell
- `frontend/src/components/upload/UploadModal.tsx` — File drop / URL input / quick note tabs

## Database

SQLite with SQLAlchemy ORM. Key tables:
- `documents` — Core knowledge items with content hash for dedup
- `document_versions` — Version history for change detection
- `categories` — Hierarchical (parent_id adjacency list)
- `entities` — Extracted named entities (person, org, concept, etc.)
- `relationships` — Entity-to-entity relations with confidence
- `knowledge_nodes` / `knowledge_edges` — Materialized graph for visualization
- `change_logs` — Change detection records with severity scoring
- `alerts` — User-facing notifications
- `summaries` — AI-generated summaries (per document or per category)

FTS5 virtual table `documents_fts` for full-text search on title + raw_text.

## Visualization

Two modes in KnowledgeGraphPage:
1. **Tree View** — D3 tree layout: categories as branches, documents as leaves
2. **Galaxy View** — D3 force simulation: categories as "stars", documents as "planets", entities as "moons"

API endpoints: `/api/v1/visualization/tree` and `/api/v1/visualization/galaxy`

## Change Detection Algorithm

When a document is re-uploaded with different content:
1. Compute content similarity (cosine on TF-IDF vectors)
2. Compute structural similarity (heading structure)
3. Compute entity set change (Jaccard distance)
4. Weighted severity score → minor/moderate/significant/major
5. "major" changes force a confirmation dialog

## State Management (Zustand)

- `useDocumentStore` — Document list, selection, CRUD operations
- `useCategoryStore` — Category tree, create/delete
- `useUIStore` — Sidebar toggle, upload modal, theme
- `useNotificationStore` — Alerts, unread count
- `useStatsStore` — Dashboard statistics
