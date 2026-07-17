import { Menu, Bell, Search as SearchIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
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
    <header className="h-14 flex items-center gap-4 px-4 border-b border-gray-800/50 bg-gray-900/80 backdrop-blur-xl">
      {/* Toggle sidebar */}
      <button onClick={toggleSidebar} className="btn-ghost p-2">
        <Menu size={20} />
      </button>

      {/* Breadcrumb — could be dynamic */}
      <div className="flex-1" />

      {/* Search bar */}
      <form onSubmit={handleSearch} className="relative w-64">
        <SearchIcon
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索知识库..."
          className="w-full pl-9 pr-4 py-1.5 bg-gray-800/50 border border-gray-700 rounded-lg
                     text-sm text-gray-200 placeholder-gray-500
                     focus:outline-none focus:border-primary-500 transition-all"
        />
      </form>

      {/* Notifications */}
      <button
        onClick={() => navigate('/documents')}
        className="relative btn-ghost p-2"
        title="通知中心"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold
                           w-4 h-4 rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
    </header>
  );
}
