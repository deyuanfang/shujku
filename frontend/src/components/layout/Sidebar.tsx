import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FileText, GitGraph, Search, Settings, Database, Upload, Folder, ChevronRight, Plus } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useCategoryStore, useUIStore } from '../../store';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/documents', icon: FileText, label: '文档' },
  { to: '/graph', icon: GitGraph, label: '图谱' },
  { to: '/search', icon: Search, label: '搜索' },
  { to: '/storage', icon: Database, label: '存储' },
  { to: '/settings', icon: Settings, label: '设置' },
];

export default function Sidebar() {
  const categories = useCategoryStore((s) => s.categories);
  const fetchCategories = useCategoryStore((s) => s.fetchCategories);
  const openUpload = useUIStore((s) => s.openUpload);
  const navigate = useNavigate();

  useEffect(() => { fetchCategories(); }, []);

  return (
    <div className="h-full flex flex-col bg-gray-900/98 border-r border-gray-800/30">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-gray-800/30">
        <h1 className="text-base font-bold text-white flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <span className="text-white text-[10px] font-black">KB</span>
          </div>
          PersonalKB
        </h1>
      </div>

      {/* Upload */}
      <div className="px-3 py-3">
        <button onClick={openUpload} className="w-full btn-primary py-2 text-sm flex items-center justify-center gap-2">
          <Upload size={15} /> 添加内容
        </button>
      </div>

      {/* Nav */}
      <nav className="px-3 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${
                isActive
                  ? 'bg-primary-600/15 text-primary-400 font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
              }`
            }
          >
            <item.icon size={17} /> {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Categories */}
      <div className="flex-1 overflow-y-auto px-3 mt-4">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-[10px] font-semibold text-gray-600 uppercase tracking-wider">分类</span>
          <button onClick={() => { const n = prompt('分类名:'); if (n) useCategoryStore.getState().createCategory(n); }}
            className="text-gray-600 hover:text-gray-300"><Plus size={13} /></button>
        </div>
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => navigate(`/documents?category_id=${cat.id}`)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-800/30 transition-all text-left"
          >
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: cat.color }} />
            <span className="flex-1 truncate text-[13px]">{cat.name}</span>
            <span className="text-[10px] text-gray-600">{cat.document_count}</span>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800/30 text-[10px] text-gray-600">
        v0.2.0
      </div>
    </div>
  );
}
