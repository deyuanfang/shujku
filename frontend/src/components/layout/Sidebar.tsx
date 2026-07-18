import { useNavigate, useLocation } from 'react-router-dom';
import { Upload, Plus, Folder, LayoutDashboard, FileText, GitGraph, Search, Database, HardDrive, Settings } from 'lucide-react';
import { useEffect } from 'react';
import FlowingMenu from '../common/FlowingMenu';
import { useCategoryStore, useUIStore } from '../../store';

const NAV_ITEMS = [
  { text: '仪表盘', link: '/', icon: <LayoutDashboard size={15} /> },
  { text: '文档', link: '/documents', icon: <FileText size={15} /> },
  { text: '图谱', link: '/graph', icon: <GitGraph size={15} /> },
  { text: '搜索', link: '/search', icon: <Search size={15} /> },
  { text: '文件', link: '/files', icon: <HardDrive size={15} /> },
  { text: '存储', link: '/storage', icon: <Database size={15} /> },
  { text: '设置', link: '/settings', icon: <Settings size={15} /> },
];

export default function Sidebar() {
  const categories = useCategoryStore((s) => s.categories);
  const fetchCategories = useCategoryStore((s) => s.fetchCategories);
  const openUpload = useUIStore((s) => s.openUpload);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => { fetchCategories(); }, []);

  const currentIndex = (() => {
    const path = location.pathname;
    const map: Record<string, number> = {
      '/': 0, '/documents': 1, '/graph': 2, '/search': 3, '/files': 4, '/storage': 5, '/settings': 6,
    };
    if (map[path] !== undefined) return map[path];
    for (const [p, i] of Object.entries(map)) {
      if (p !== '/' && path.startsWith(p)) return i;
    }
    return null;
  })();

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

      {/* Flowing menu navigation */}
      <div className="flex-1">
        <FlowingMenu
          items={NAV_ITEMS}
          speed={12}
          textColor="#6b7280"
          bgColor="transparent"
          marqueeBgColor="#6366f1"
          marqueeTextColor="#fff"
          borderColor="rgba(255,255,255,0.04)"
          activeIndex={currentIndex}
          onItemClick={(idx, item) => navigate(item.link)}
        />
      </div>

      {/* Categories */}
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

      <div className="px-4 py-2.5 border-t border-white/[0.04] text-[9px] text-gray-700">v0.3.0</div>
    </div>
  );
}
