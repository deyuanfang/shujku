import { Menu, Bell, Search as SearchIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import Breadcrumb from './Breadcrumb';
import { useUIStore, useNotificationStore } from '../../store';

export default function Header() {
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <header className="h-14 flex items-center gap-3 px-4 border-b border-white/[0.04] bg-[#0a0a14]/90 backdrop-blur-xl">
      {/* Toggle sidebar */}
      <button onClick={toggleSidebar} className="p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/[0.04] transition-all">
        <Menu size={19} />
      </button>

      {/* Breadcrumb navigation */}
      <div className="flex-1">
        <Breadcrumb />
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="relative w-52 hidden md:block">
        <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索…"
          className="w-full pl-8 pr-3 py-1.5 bg-white/[0.03] border border-white/[0.06] rounded-lg
                     text-sm text-gray-200 placeholder-gray-600
                     focus:outline-none focus:border-indigo-500/50 transition-all"
        />
      </form>

      {/* Alerts */}
      <button onClick={() => navigate('/documents')} className="relative p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/[0.04] transition-all">
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[9px] font-bold
                           w-4 h-4 rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
    </header>
  );
}
