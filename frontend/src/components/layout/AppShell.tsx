import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import UploadModal from '../upload/UploadModal';
import QuickCapture from '../upload/QuickCapture';
import MobileImport from '../upload/MobileImport';
import { useUIStore } from '../../store';

export default function AppShell() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const uploadModalOpen = useUIStore((s) => s.uploadModalOpen);

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`
          fixed lg:relative z-40 h-full transition-transform duration-300
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:-translate-x-[280px]'}
          w-[280px] flex-shrink-0
        `}
      >
        <Sidebar />
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      {/* Upload modal */}
      {uploadModalOpen && <UploadModal />}

      {/* Quick capture floating button */}
      <QuickCapture />
      {/* Mobile import floating button */}
      <MobileImport />

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={useUIStore.getState().toggleSidebar}
        />
      )}
    </div>
  );
}
