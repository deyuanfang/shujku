// ── Document Types ──────────────────────────

export type ContentType = 'text' | 'markdown' | 'pdf' | 'image' | 'url' | 'note';

export interface DocumentItem {
  id: string;
  title: string;
  content_type: ContentType;
  source_path?: string;
  source_url?: string;
  original_hash: string;
  word_count: number;
  char_count: number;
  category_id?: string;
  importance: number;
  created_at: string;
  updated_at: string;
  last_analyzed_at?: string;
}

export interface DocumentDetail extends DocumentItem {
  raw_text?: string;
  summary?: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UploadResult {
  status: string;
  document_id: string;
  title: string;
  content_type: string;
  category: string;
  confidence: number;
  keywords: string[];
}

// ── Category Types ──────────────────────────

export interface Category {
  id: string;
  name: string;
  parent_id?: string;
  description?: string;
  color: string;
  icon: string;
  document_count: number;
  created_at: string;
  children?: CategoryTree[];
}

export interface CategoryTree extends Category {
  children: CategoryTree[];
}

// ── Visualization Types ──────────────────────

export interface TreeNode {
  id: string;
  label: string;
  type: 'category' | 'document';
  color?: string;
  count?: number;
  importance?: number;
  content_type?: string;
  word_count?: number;
  children?: TreeNode[];
}

export interface GalaxyNode {
  id: string;
  refId: string;
  label: string;
  type: 'category' | 'document' | 'entity';
  importance: number;
  x?: number;
  y?: number;
  radius: number;
  color?: string;
  clusterId?: string;
  entityType?: string;
  contentType?: string;
}

export interface GalaxyEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface GalaxyData {
  galaxy: {
    nodes: GalaxyNode[];
    edges: GalaxyEdge[];
  };
}

// ── Search Types ────────────────────────────

export interface SearchResult {
  id: string;
  title: string;
  content_type: string;
  category_id?: string;
  snippet: string;
  created_at: string;
  word_count: number;
}

// ── Stats Types ─────────────────────────────

export interface DashboardStats {
  total_documents: number;
  total_categories: number;
  total_entities: number;
  total_words: number;
  documents_by_type: Record<string, number>;
  top_categories: Array<{ name: string; count: number }>;
}

// ── Change/Alert Types ──────────────────────

export interface ChangeLog {
  id: string;
  document_id: string;
  severity: number;
  severity_label: 'minor' | 'moderate' | 'significant' | 'major';
  content_diff?: string;
  entity_changes?: string;
  is_confirmed: boolean;
  created_at: string;
}

export interface Alert {
  id: string;
  title: string;
  message: string;
  alert_type: 'change' | 'conflict' | 'review' | 'system';
  severity: string;
  is_read: boolean;
  related_item_id?: string;
  created_at: string;
}
