import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import UploadModal from '../upload/UploadModal';
import QuickCapture from '../upload/QuickCapture';
import MobileImport from '../upload/MobileImport';
import DotField from '../background/DotField';
import { useUIStore } from '../../store';

export default function AppShell() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const uploadModalOpen = useUIStore((s) => s.uploadModalOpen);

  return (
    <div className="flex h-screen bg-[#0a0a14] overflow-hidden relative">
      {/* Animated dot grid background */}
      <DotField
        dotRadius={1.5}
        dotSpacing={16}
        bulgeStrength={72}
        glowRadius={180}
        sparkle
        waveAmplitude={0.8}
        gradientFrom="rgba(99, 102, 241, 0.22)"
        gradientTo="rgba(139, 92, 246, 0.12)"
        glowColor="#0f0f23"
      />

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:relative z-30 h-full transition-transform duration-300
          bg-[#0a0a18]/95 backdrop-blur-xl border-r border-white/5
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:-translate-x-[280px]'}
          w-[280px] flex-shrink-0
        `}
      >
        <Sidebar />
      </aside>

      {/* Main area */}
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

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={useUIStore.getState().toggleSidebar}
        />
      )}
    </div>
  );
}
