import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, FolderTree, BookOpen, TrendingUp,
  Plus, Search, Zap, ArrowRight, Sparkles,
  FileCode, FileImage, Globe, StickyNote,
} from 'lucide-react';
import { useStatsStore, useDocumentStore, useUIStore } from '../store';

const TYPE_ICONS: Record<string, any> = {
  text: FileText, markdown: FileCode, pdf: FileText,
  image: FileImage, url: Globe, note: StickyNote,
};
const TYPE_COLORS: Record<string, string> = {
  text: 'from-blue-600/20 to-blue-800/10 border-blue-600/30',
  markdown: 'from-violet-600/20 to-violet-800/10 border-violet-600/30',
  pdf: 'from-red-600/20 to-red-800/10 border-red-600/30',
  image: 'from-emerald-600/20 to-emerald-800/10 border-emerald-600/30',
  url: 'from-cyan-600/20 to-cyan-800/10 border-cyan-600/30',
  note: 'from-amber-600/20 to-amber-800/10 border-amber-600/30',
};
const TYPE_LABELS: Record<string, string> = {
  text: '文本', markdown: 'MD', pdf: 'PDF', image: '图片', url: '网页', note: '笔记',
};

export default function DashboardPage() {
  const stats = useStatsStore((s) => s.stats);
  const fetchStats = useStatsStore((s) => s.fetchStats);
  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const openUpload = useUIStore((s) => s.openUpload);
  const navigate = useNavigate();

  useEffect(() => {
    fetchStats();
    fetchDocuments({ page_size: 8, sort_by: 'created_at', sort_order: 'desc' });
  }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-fade-in">
      {/* Hero section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-gray-900 via-gray-900 to-primary-950 border border-gray-800/50 p-8">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary-600/10 rounded-full blur-3xl" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Sparkles size={28} className="text-primary-400" />
              知识库
            </h1>
            <p className="text-gray-400 mt-2 text-lg">
              {stats?.total_documents
                ? `${stats.total_documents} 篇文档 · ${stats.total_categories} 个分类`
                : '开始构建你的第二大脑'}
            </p>
            <div className="flex gap-3 mt-5">
              <button onClick={openUpload} className="btn-primary flex items-center gap-2 px-5 py-2.5 text-sm">
                <Plus size={18} /> 添加内容
              </button>
              <button onClick={() => navigate('/search')} className="btn-secondary flex items-center gap-2 px-5 py-2.5 text-sm">
                <Search size={16} /> 搜索知识
              </button>
            </div>
          </div>
          <div className="hidden lg:flex gap-3">
            {['note', 'markdown', 'pdf', 'image', 'url'].map((type) => {
              const Icon = TYPE_ICONS[type] || FileText;
              const count = stats?.documents_by_type?.[type] || 0;
              return (
                <div key={type} className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl bg-gradient-to-b border ${TYPE_COLORS[type] || ''}`}>
                  <Icon size={18} />
                  <span className="text-xs font-bold">{count}</span>
                  <span className="text-[10px] text-gray-500">{TYPE_LABELS[type]}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: '文档', value: stats?.total_documents ?? 0, icon: FileText, color: 'text-primary-400', bg: 'bg-primary-600/10' },
          { label: '分类', value: stats?.total_categories ?? 0, icon: FolderTree, color: 'text-emerald-400', bg: 'bg-emerald-600/10' },
          { label: '实体', value: stats?.total_entities ?? 0, icon: TrendingUp, color: 'text-amber-400', bg: 'bg-amber-600/10' },
          { label: '万字', value: stats?.total_words ? (stats.total_words / 10000).toFixed(1) : '0', icon: BookOpen, color: 'text-pink-400', bg: 'bg-pink-600/10' },
        ].map((s) => (
          <div key={s.label} className="glass-panel p-4 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${s.bg} flex items-center justify-center`}>
              <s.icon size={20} className={s.color} />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-xs text-gray-500">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent documents */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Zap size={18} className="text-primary-400" /> 最近文档
          </h2>
          <button onClick={() => navigate('/documents')} className="text-sm text-primary-400 hover:text-primary-300 flex items-center gap-1">
            全部 <ArrowRight size={14} />
          </button>
        </div>

        {documents.length === 0 ? (
          <button onClick={openUpload} className="w-full glass-panel p-12 text-center hover:border-gray-600 transition-all group">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-primary-600/10 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Plus size={28} className="text-primary-400" />
            </div>
            <p className="text-gray-400 font-medium">添加你的第一条知识</p>
            <p className="text-gray-600 text-sm mt-1">支持文本、Markdown、PDF、图片、网页链接</p>
          </button>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {documents.slice(0, 8).map((doc) => {
              const Icon = TYPE_ICONS[doc.content_type] || FileText;
              return (
                <div
                  key={doc.id}
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  className={`group cursor-pointer rounded-xl border bg-gradient-to-b p-4 transition-all hover:scale-[1.02] hover:shadow-lg ${TYPE_COLORS[doc.content_type] || 'border-gray-700/50'}`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <Icon size={20} className="opacity-70" />
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800/50 text-gray-500">
                      {doc.word_count}字
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-gray-200 line-clamp-2 group-hover:text-white transition-colors">
                    {doc.title}
                  </h3>
                  <p className="text-[10px] text-gray-600 mt-2">
                    {doc.created_at?.slice(0, 10)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Categories */}
      {stats?.top_categories && stats.top_categories.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <FolderTree size={18} className="text-emerald-400" /> 分类概览
          </h2>
          <div className="flex flex-wrap gap-2">
            {stats.top_categories.map((cat, i) => (
              <button
                key={cat.name}
                onClick={() => navigate(`/documents?category_id=${cat.name}`)}
                className="flex items-center gap-2 px-4 py-2 rounded-full border border-gray-700/50
                           bg-gray-800/30 hover:bg-gray-800/50 hover:border-gray-600 transition-all text-sm"
              >
                <span className="w-2 h-2 rounded-full" style={{ background: ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6'][i % 5] }} />
                <span className="text-gray-300">{cat.name}</span>
                <span className="text-xs text-gray-600">{cat.count}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
