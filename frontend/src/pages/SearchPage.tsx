import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Search, FileText, Loader2 } from 'lucide-react';
import { searchDocuments } from '../services/api';
import type { SearchResult } from '../types';

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryParam = searchParams.get('q') || '';
  const [query, setQuery] = useState(queryParam);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (queryParam) {
      setQuery(queryParam);
      doSearch(queryParam);
    }
  }, [queryParam]);

  async function doSearch(q: string) {
    if (!q.trim()) return;
    setIsLoading(true);
    try {
      const data = await searchDocuments(q.trim());
      setResults(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error('Search failed:', err);
    }
    setIsLoading(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
      doSearch(query.trim());
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold text-white">全文搜索</h1>

      <form onSubmit={handleSubmit} className="relative">
        <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入关键词搜索知识库..."
          className="w-full pl-12 pr-4 py-3 bg-gray-900/80 border border-gray-700 rounded-xl
                     text-gray-100 placeholder-gray-500 text-lg
                     focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500
                     transition-all"
        />
      </form>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-primary-400" />
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            找到 <span className="text-gray-300 font-medium">{total}</span> 条结果
          </p>
          {results.map((item) => (
            <div
              key={item.id}
              onClick={() => navigate(`/documents/${item.id}`)}
              className="glass-panel p-5 hover:border-gray-700 cursor-pointer transition-all group"
            >
              <div className="flex items-start gap-3">
                <FileText size={18} className="text-gray-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-gray-200 group-hover:text-primary-400 transition-all">
                    {item.title}
                  </h3>
                  {item.snippet && (
                    <p
                      className="text-sm text-gray-400 mt-1.5 leading-relaxed"
                      dangerouslySetInnerHTML={{ __html: item.snippet }}
                    />
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-600">
                    <span>{item.content_type}</span>
                    <span>{item.word_count} 字</span>
                    <span>{item.created_at?.slice(0, 10)}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : queryParam ? (
        <div className="glass-panel p-16 text-center">
          <Search size={48} className="mx-auto mb-4 text-gray-600" />
          <p className="text-gray-400">未找到相关结果</p>
          <p className="text-gray-500 text-sm mt-2">尝试使用不同的关键词搜索</p>
        </div>
      ) : (
        <div className="glass-panel p-16 text-center">
          <Search size={48} className="mx-auto mb-4 text-gray-600" />
          <p className="text-gray-400">输入关键词开始搜索</p>
          <p className="text-gray-500 text-sm mt-2">支持全文搜索，可搜索文档标题和内容</p>
        </div>
      )}
    </div>
  );
}
