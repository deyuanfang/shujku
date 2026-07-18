import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import UploadModal from '../upload/UploadModal';
import QuickCapture from '../upload/QuickCapture';
import MobileImport from '../upload/MobileImport';
import AIDashboard from '../knowledge/AIDashboard';
import LetterGlitch from '../background/LetterGlitch';
import { useUIStore } from '../../store';

export default function AppShell() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const uploadModalOpen = useUIStore((s) => s.uploadModalOpen);

  return (
    <div className="flex h-screen bg-[#0a0a14] overflow-hidden relative">
      {/* Letter glitch background */}
      <LetterGlitch
        glitchColors={['#1e1b4b', '#312e81', '#6366f1']}
        glitchSpeed={45}
        centerVignette
        outerVignette
        smooth
      />

      {/* Sidebar — collapses to 0 width when closed */}
      <aside
        className={`h-full flex-shrink-0 overflow-hidden transition-all duration-300 z-30
          bg-[#0a0a18]/95 backdrop-blur-xl border-r border-white/5
          ${sidebarOpen ? 'w-[260px]' : 'w-0 border-r-0'}`}
      >
        <div className="w-[260px] h-full">
          <Sidebar />
        </div>
      </aside>

      {/* Main area — fills remaining space */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      {/* Upload modal */}
      {uploadModalOpen && <UploadModal />}

      {/* Floating action buttons */}
      <QuickCapture />
      <MobileImport />
      {/* AI status dashboard */}
      <AIDashboard />
    </div>
  );
}
