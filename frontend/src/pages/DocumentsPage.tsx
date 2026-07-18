import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { FileText, Trash2, Search, StickyNote, Globe, FileCode, FileImage, AlertTriangle, ChevronDown, ChevronRight, FolderOpen } from 'lucide-react';
import { useDocumentStore, useCategoryStore } from '../store';
import { showToast } from '../components/common/Toast';
import api from '../services/api';

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
  const categories = useCategoryStore((s) => s.categories);
  const fetchCategories = useCategoryStore((s) => s.fetchCategories);
  const [filterType, setFilterType] = useState('');
  const [quickSearch, setQuickSearch] = useState('');
  const [clearing, setClearing] = useState(false);
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set());

  // Auto-expand all categories when documents load
  useEffect(() => {
    const ids = new Set<string>();
    for (const doc of documents) {
      ids.add(doc.category_id || '__uncat__');
    }
    if (ids.size > 0) setExpandedCats(ids);
  }, [documents.length]);

  useEffect(() => {
    fetchDocuments({
      category_id: searchParams.get('category_id') || undefined,
      content_type: filterType || undefined,
      search: quickSearch || undefined,
      page_size: 200, sort_by: 'updated_at', sort_order: 'desc',
    });
    fetchCategories();
  }, [searchParams, filterType, quickSearch]);

  const handleClearAll = async () => {
    if (!confirm('确定要清空所有文档？此操作不可撤销！')) return;
    const phrase = prompt('请输入: 确认清空所有数据');
    if (phrase !== '确认清空所有数据') { showToast('error', '短语不匹配，已取消'); return; }
    setClearing(true);
    try {
      await api.post('/manage/clear-all', null, { params: { confirm: '确认清空所有数据' } });
      showToast('success', '所有数据已清空');
      fetchDocuments({ page_size: 200, sort_by: 'updated_at', sort_order: 'desc' });
    } catch (err: any) { showToast('error', '清空失败', err.message); }
    setClearing(false);
  };

  const toggleCat = (id: string) => {
    setExpandedCats((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // Group documents by category
  const catMap = new Map<string, { name: string; color: string; docs: any[] }>();
  for (const doc of documents) {
    const cid = doc.category_id || '__uncat__';
    if (!catMap.has(cid)) {
      const cat = categories.find((c) => c.id === cid);
      catMap.set(cid, {
        name: cid === '__uncat__' ? '未分类' : (cat?.name || '未知分类'),
        color: cid === '__uncat__' ? '#6b7280' : (cat?.color || '#6366f1'),
        docs: [],
      });
    }
    catMap.get(cid)!.docs.push(doc);
  }

  const allExpanded = catMap.size > 0 && [...catMap.keys()].every((k) => expandedCats.has(k));
  const sortedCats = [...catMap.entries()].sort((a, b) => b[1].docs.length - a[1].docs.length);

  return (
    <div className="max-w-6xl mx-auto space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">文档</h1>
          <p className="text-gray-500 text-sm mt-0.5">{total} 篇 · {catMap.size} 个分类</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => {
            if (allExpanded) { setExpandedCats(new Set()); }
            else { setExpandedCats(new Set([...catMap.keys()])); }
          }}
            className="text-xs text-gray-500 hover:text-gray-300 transition-all">
            {allExpanded ? '折叠全部' : '展开全部'}
          </button>
          <button onClick={handleClearAll} disabled={clearing || total === 0}
            className="flex items-center gap-1 px-2 py-1 text-xs rounded-lg
                       bg-red-600/10 border border-red-600/20 text-red-400
                       hover:bg-red-600/20 transition-all disabled:opacity-30">
            <AlertTriangle size={11} /> 清空
          </button>
          <div className="relative w-40">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
            <input value={quickSearch} onChange={(e) => setQuickSearch(e.target.value)}
              placeholder="筛选..." className="w-full pl-7 pr-3 py-1.5 bg-gray-800/50 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:border-primary-500" />
          </div>
        </div>
      </div>

      {/* Type filter pills */}
      <div className="flex gap-1.5 flex-wrap">
        {[['', '全部'],['note','笔记'],['markdown','MD'],['text','TXT'],['pdf','PDF'],['url','网页'],['image','图片']].map(([type, label]) => (
          <button key={type} onClick={() => setFilterType(type)}
            className={`px-2.5 py-1 text-xs rounded-full transition-all ${
              filterType === type ? 'bg-primary-600 text-white' : 'bg-gray-800/50 text-gray-400 hover:text-gray-200'
            }`}>{label}</button>
        ))}
      </div>

      {/* Category sections */}
      {isLoading ? (
        <div className="flex justify-center py-16"><div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" /></div>
      ) : documents.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <FileText size={36} className="mx-auto mb-3 text-gray-600" />
          <p className="text-gray-400">{quickSearch ? '无匹配文档' : '还没有文档'}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sortedCats.map(([cid, group]) => {
            const isExpanded = allExpanded || expandedCats.has(cid);
            return (
              <div key={cid} className="glass-panel overflow-hidden">
                {/* Category header */}
                <button
                  onClick={() => toggleCat(cid)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-all"
                >
                  {isExpanded ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-500" />}
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: group.color }} />
                  <span className="text-sm font-medium text-gray-200">{group.name}</span>
                  <span className="text-xs text-gray-600 ml-auto">{group.docs.length} 篇</span>
                </button>

                {/* Documents in this category */}
                {isExpanded && (
                  <div className="border-t border-white/[0.04]">
                    {group.docs.map((doc) => {
                      const Icon = TYPE_ICONS[doc.content_type] || FileText;
                      const colorClass = TYPE_COLORS[doc.content_type] || '';
                      return (
                        <div
                          key={doc.id}
                          onClick={() => navigate(`/documents/${doc.id}`)}
                          className="flex items-center gap-3 px-5 py-2 hover:bg-white/[0.03] cursor-pointer transition-all group border-b border-white/[0.02] last:border-0"
                        >
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0 ${colorClass}`}>
                            <Icon size={10} />{TYPE_LABELS[doc.content_type] || doc.content_type}
                          </span>
                          <span className="flex-1 text-sm text-gray-300 truncate group-hover:text-white transition-colors">
                            {doc.title}
                          </span>
                          <span className="text-[10px] text-gray-600 flex-shrink-0">{doc.word_count}字</span>
                          <span className="text-[10px] text-gray-700 flex-shrink-0 w-16 text-right">{doc.created_at?.slice(0, 10)}</span>
                          <button
                            onClick={(e) => { e.stopPropagation(); if (confirm('删除？')) deleteDocument(doc.id); }}
                            className="opacity-0 group-hover:opacity-100 ml-1 p-1 hover:bg-red-600/20 rounded transition-all flex-shrink-0"
                          >
                            <Trash2 size={11} className="text-red-400" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
