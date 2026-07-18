import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import AppShell from './components/layout/AppShell';
import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import DocumentDetailPage from './pages/DocumentDetailPage';
import KnowledgeGraphPage from './pages/KnowledgeGraphPage';
import SearchPage from './pages/SearchPage';
import SettingsPage from './pages/SettingsPage';
import StoragePage from './pages/StoragePage';
import SetupWizardPage from './pages/SetupWizardPage';
import FileManagerPage from './pages/FileManagerPage';
import ToastContainer, { useToastStore } from './components/common/Toast';
import { useCategoryStore, useNotificationStore } from './store';

export default function App() {
  const fetchCategories = useCategoryStore((s) => s.fetchCategories);
  const fetchAlerts = useNotificationStore((s) => s.fetchAlerts);
  const { toasts, dismiss } = useToastStore();

  useEffect(() => {
    fetchCategories();
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
          <Route path="/graph" element={<KnowledgeGraphPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/storage" element={<StoragePage />} />
          <Route path="/setup" element={<SetupWizardPage />} />
          <Route path="/files" element={<FileManagerPage />} />
        </Route>
      </Routes>
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </BrowserRouter>
  );
}
