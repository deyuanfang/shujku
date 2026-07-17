import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { FileText, Trash2, Search, StickyNote, Globe, FileCode, FileImage } from 'lucide-react';
import { useDocumentStore } from '../store';

const TYPE_ICONS: Record<string, any> = {
  text: FileText, markdown: FileCode, pdf: FileText, image: FileImage, url: Globe, note: StickyNote,
};
const TYPE_COLORS: Record<string, string> = {
  text: 'text-blue-400 bg-blue-600/10', markdown: 'text-violet-400 bg-violet-600/10',
  pdf: 'text-red-400 bg-red-600/10', image: 'text-emerald-400 bg-emerald-600/10',
  url: 'text-cyan-400 bg-cyan-600/10', note: 'text-amber-400 bg-amber-600/10',
};
const TYPE_LABELS: Record<string, string> = {
  text: 'TXT', markdown: 'MD', pdf: 'PDF', image: 'IMG', url: 'URL', note: '笔记',
};

export default function DocumentsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { documents, total, isLoading, fetchDocuments, deleteDocument } = useDocumentStore();
  const [filterType, setFilterType] = useState('');
  const [quickSearch, setQuickSearch] = useState('');

  useEffect(() => {
    fetchDocuments({
      category_id: searchParams.get('category_id') || undefined,
      content_type: filterType || undefined,
      search: quickSearch || undefined,
      page_size: 50, sort_by: 'updated_at', sort_order: 'desc',
    });
  }, [searchParams, filterType, quickSearch]);

  return (
    <div className="max-w-6xl mx-auto space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">文档</h1>
          <p className="text-gray-500 text-sm mt-0.5">{total} 篇</p>
        </div>
        <div className="relative w-56">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={quickSearch}
            onChange={(e) => setQuickSearch(e.target.value)}
            placeholder="快速筛选..."
            className="w-full pl-8 pr-3 py-1.5 bg-gray-800/50 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-primary-500"
          />
        </div>
      </div>

      {/* Type filter pills */}
      <div className="flex gap-1.5 flex-wrap">
        {[
          ['', '全部'],
          ['note', '笔记'], ['markdown', 'Markdown'], ['text', '文本'],
          ['pdf', 'PDF'], ['url', '网页'], ['image', '图片'],
        ].map(([type, label]) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            className={`px-3 py-1 text-xs rounded-full transition-all ${
              filterType === type
                ? 'bg-primary-600 text-white'
                : 'bg-gray-800/50 text-gray-400 hover:text-gray-200 hover:bg-gray-800'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Document grid */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : documents.length === 0 ? (
        <div className="glass-panel p-16 text-center">
          <FileText size={40} className="mx-auto mb-3 text-gray-600" />
          <p className="text-gray-400">{quickSearch ? '没有匹配的文档' : '还没有文档'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {documents.map((doc) => {
            const Icon = TYPE_ICONS[doc.content_type] || FileText;
            const colorClass = TYPE_COLORS[doc.content_type] || '';
            return (
              <div
                key={doc.id}
                onClick={() => navigate(`/documents/${doc.id}`)}
                className="group glass-panel p-4 cursor-pointer hover:border-gray-600 transition-all hover:scale-[1.01]"
              >
                <div className="flex items-start justify-between mb-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${colorClass}`}>
                    <Icon size={12} />
                    {TYPE_LABELS[doc.content_type] || doc.content_type}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); if (confirm('删除？')) deleteDocument(doc.id); }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-600/20 rounded transition-all"
                  >
                    <Trash2 size={12} className="text-red-400" />
                  </button>
                </div>
                <h3 className="text-sm font-medium text-gray-200 line-clamp-2 mb-2 group-hover:text-white transition-colors">
                  {doc.title}
                </h3>
                <div className="flex items-center justify-between text-[10px] text-gray-600">
                  <span>{doc.word_count} 字</span>
                  <span>{doc.created_at?.slice(0, 10)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
