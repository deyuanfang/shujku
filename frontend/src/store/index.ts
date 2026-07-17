import { create } from 'zustand';
import type { DocumentItem, DocumentDetail, CategoryTree, DashboardStats, Alert } from '../types';
import * as api from '../services/api';

// ── Document Store ──────────────────────────────

interface DocumentStore {
  documents: DocumentItem[];
  selectedDoc: DocumentDetail | null;
  total: number;
  page: number;
  isLoading: boolean;
  error: string | null;

  fetchDocuments: (params?: Record<string, any>) => Promise<void>;
  fetchDocument: (id: string) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  clearSelected: () => void;
}

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  documents: [],
  selectedDoc: null,
  total: 0,
  page: 1,
  isLoading: false,
  error: null,

  fetchDocuments: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const data = await api.fetchDocuments(params);
      set({
        documents: data.items,
        total: data.total,
        page: data.page,
        isLoading: false,
      });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  fetchDocument: async (id) => {
    set({ isLoading: true });
    try {
      const doc = await api.fetchDocument(id);
      set({ selectedDoc: doc, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  deleteDocument: async (id) => {
    await api.deleteDocument(id);
    set((s) => ({
      documents: s.documents.filter((d) => d.id !== id),
      total: s.total - 1,
    }));
  },

  clearSelected: () => set({ selectedDoc: null }),
}));

// ── Category Store ──────────────────────────────

interface CategoryStore {
  categories: CategoryTree[];
  isLoading: boolean;

  fetchCategories: () => Promise<void>;
  createCategory: (name: string, parentId?: string) => Promise<void>;
  deleteCategory: (id: string) => Promise<void>;
}

export const useCategoryStore = create<CategoryStore>((set) => ({
  categories: [],
  isLoading: false,

  fetchCategories: async () => {
    set({ isLoading: true });
    try {
      const categories = await api.fetchCategories(true);
      set({ categories, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  createCategory: async (name, parentId) => {
    await api.createCategory(name, parentId);
    const categories = await api.fetchCategories(true);
    set({ categories });
  },

  deleteCategory: async (id) => {
    await api.deleteCategory(id);
    const categories = await api.fetchCategories(true);
    set({ categories });
  },
}));

// ── UI Store ────────────────────────────────────

interface UIStore {
  sidebarOpen: boolean;
  uploadModalOpen: boolean;
  theme: 'dark' | 'light' | 'system';
  toggleSidebar: () => void;
  openUpload: () => void;
  closeUpload: () => void;
  setTheme: (theme: 'dark' | 'light' | 'system') => void;
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarOpen: true,
  uploadModalOpen: false,
  theme: 'dark',

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  openUpload: () => set({ uploadModalOpen: true }),
  closeUpload: () => set({ uploadModalOpen: false }),
  setTheme: (theme) => set({ theme }),
}));

// ── Notification Store ──────────────────────────

interface NotificationStore {
  alerts: Alert[];
  unreadCount: number;
  isLoading: boolean;

  fetchAlerts: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  alerts: [],
  unreadCount: 0,
  isLoading: false,

  fetchAlerts: async () => {
    set({ isLoading: true });
    try {
      const data = await api.fetchAlerts(false);
      set({ alerts: data.items, unreadCount: data.unread_count, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  markRead: async (id) => {
    await api.markAlertRead(id);
    set((s) => ({
      alerts: s.alerts.map((a) => (a.id === id ? { ...a, is_read: true } : a)),
      unreadCount: Math.max(0, s.unreadCount - 1),
    }));
  },

  markAllRead: async () => {
    await api.markAllAlertsRead();
    set((s) => ({
      alerts: s.alerts.map((a) => ({ ...a, is_read: true })),
      unreadCount: 0,
    }));
  },
}));

// ── Stats Store ─────────────────────────────────

interface StatsStore {
  stats: DashboardStats | null;
  isLoading: boolean;
  fetchStats: () => Promise<void>;
}

export const useStatsStore = create<StatsStore>((set) => ({
  stats: null,
  isLoading: false,
  fetchStats: async () => {
    set({ isLoading: true });
    try {
      const stats = await api.fetchStats();
      set({ stats, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },
}));
