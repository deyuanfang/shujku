import { useNavigate, useLocation } from 'react-router-dom';
import { Upload, Plus, Folder, HardDrive } from 'lucide-react';
import { useEffect } from 'react';
import LineSidebar from '../common/LineSidebar';
import { useCategoryStore, useUIStore } from '../../store';

export default function Sidebar() {
  const categories = useCategoryStore((s) => s.categories);
  const fetchCategories = useCategoryStore((s) => s.fetchCategories);
  const openUpload = useUIStore((s) => s.openUpload);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => { fetchCategories(); }, []);

  const navItems = ['仪表盘', '文档', '图谱', '搜索', '文件', '存储', '设置'];
  const navRoutes: Record<string, string> = {
    '仪表盘': '/', '文档': '/documents', '图谱': '/graph',
    '搜索': '/search', '文件': '/files', '存储': '/storage', '设置': '/settings',
  };

  const currentIndex = (() => {
    const path = location.pathname;
    if (path === '/') return 0;
    if (path.startsWith('/documents')) return 1;
    if (path.startsWith('/graph')) return 2;
    if (path.startsWith('/search')) return 3;
    if (path.startsWith('/storage')) return 4;
    if (path.startsWith('/settings')) return 5;
    return null;
  })();

  const handleNavClick = (index: number, label: string) => {
    const route = navRoutes[label];
    if (route) navigate(route);
  };

  return (
    <div className="h-full flex flex-col bg-[#060610]/98 border-r border-white/[0.04] backdrop-blur-xl">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-white/[0.04]">
        <h1 className="text-sm font-bold text-white/90 flex items-center gap-2 tracking-tight">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <span className="text-white text-[9px] font-black">KB</span>
          </div>
          PersonalKB
        </h1>
      </div>

      {/* Upload */}
      <div className="px-4 py-3">
        <button onClick={openUpload}
          className="w-full py-2 text-xs font-medium rounded-xl
                     bg-gradient-to-r from-indigo-600/80 to-purple-600/80
                     hover:from-indigo-500 hover:to-purple-500
                     text-white flex items-center justify-center gap-2
                     transition-all active:scale-[0.97]">
          <Upload size={13} /> 添加内容
        </button>
      </div>

      {/* Animated nav */}
      <div className="flex-1 px-3 py-2">
        <LineSidebar
          items={navItems}
          accentColor="#818cf8"
          textColor="#6b7280"
          markerColor="#374151"
          showIndex
          showMarker
          proximityRadius={90}
          maxShift={22}
          falloff="smooth"
          markerLength={44}
          markerGap={4}
          tickScale={0.4}
          scaleTick
          itemGap={8}
          fontSize={0.88}
          smoothing={130}
          defaultActive={currentIndex}
          onItemClick={handleNavClick}
        />
      </div>

      {/* Categories (simple, below animated nav) */}
      <div className="px-4 pb-4 border-t border-white/[0.04]">
        <div className="flex items-center justify-between mt-3 mb-1.5">
          <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-widest">分类</span>
          <button onClick={() => { const n = prompt('分类名:'); if (n) useCategoryStore.getState().createCategory(n); }}
            className="text-gray-600 hover:text-gray-400"><Plus size={12} /></button>
        </div>
        <div className="space-y-0.5 max-h-32 overflow-y-auto">
          {categories.slice(0, 8).map((cat) => (
            <button key={cat.id}
              onClick={() => navigate(`/documents?category_id=${cat.id}`)}
              className="w-full flex items-center gap-2 px-2 py-1 rounded-md text-[11px]
                         text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] transition-all text-left">
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cat.color }} />
              <span className="flex-1 truncate">{cat.name}</span>
              <span className="text-[9px] text-gray-700">{cat.document_count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Version */}
      <div className="px-4 py-2.5 border-t border-white/[0.04] text-[9px] text-gray-700">
        v0.3.0
      </div>
    </div>
  );
}
