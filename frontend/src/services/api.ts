import axios from 'axios';
import type {
  DocumentListResponse,
  DocumentDetail,
  UploadResult,
  CategoryTree,
  DashboardStats,
  SearchResult,
  GalaxyData,
  TreeNode,
  ChangeLog,
  Alert,
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Upload ──────────────────────────────────────

export async function uploadFile(formData: FormData): Promise<UploadResult> {
  const { data } = await api.post('/upload/file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function uploadURL(url: string): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('url', url);
  const { data } = await api.post('/upload/url', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function uploadNote(text: string, title?: string): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('text', text);
  if (title) formData.append('title', title);
  const { data } = await api.post('/upload/note', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// ── Documents ───────────────────────────────────

export async function fetchDocuments(params?: {
  category_id?: string;
  content_type?: string;
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: string;
}): Promise<DocumentListResponse> {
  const { data } = await api.get('/documents', { params });
  return data;
}

export async function fetchDocument(id: string): Promise<DocumentDetail> {
  const { data } = await api.get(`/documents/${id}`);
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`);
}

// ── Categories ──────────────────────────────────

export async function fetchCategories(tree = true): Promise<CategoryTree[]> {
  const { data } = await api.get('/categories', { params: { tree } });
  return data;
}

export async function createCategory(name: string, parent_id?: string): Promise<CategoryTree> {
  const { data } = await api.post('/categories', null, { params: { name, parent_id } });
  return data;
}

export async function deleteCategory(id: string, reassign_to?: string): Promise<void> {
  await api.delete(`/categories/${id}`, { params: { reassign_to } });
}

// ── Search ──────────────────────────────────────

export async function searchDocuments(q: string, page = 1, page_size = 20) {
  const { data } = await api.get('/search', { params: { q, page, page_size } });
  return data as { items: SearchResult[]; total: number; page: number; page_size: number; query: string };
}

// ── Visualization ───────────────────────────────

export async function fetchTreeData(): Promise<{ tree: TreeNode }> {
  const { data } = await api.get('/visualization/tree');
  return data;
}

export async function fetchGalaxyData(): Promise<GalaxyData> {
  const { data } = await api.get('/visualization/galaxy');
  return data;
}

// ── Stats ───────────────────────────────────────

export async function fetchStats(): Promise<DashboardStats> {
  const { data } = await api.get('/stats');
  return data;
}

// ── Changes & Alerts ────────────────────────────

export async function fetchChangeLogs(params?: {
  document_id?: string;
  is_confirmed?: boolean;
}): Promise<{ items: ChangeLog[] }> {
  const { data } = await api.get('/changes/logs', { params });
  return data;
}

export async function confirmChange(logId: string): Promise<void> {
  await api.post(`/changes/logs/${logId}/confirm`);
}

export async function dismissChange(logId: string): Promise<void> {
  await api.post(`/changes/logs/${logId}/dismiss`);
}

export async function fetchAlerts(is_read?: boolean): Promise<{ items: Alert[]; unread_count: number }> {
  const { data } = await api.get('/changes/alerts', { params: { is_read } });
  return data;
}

export async function markAlertRead(alertId: string): Promise<void> {
  await api.post(`/changes/alerts/${alertId}/read`);
}

export async function markAllAlertsRead(): Promise<void> {
  await api.post('/changes/alerts/read-all');
}

export default api;
