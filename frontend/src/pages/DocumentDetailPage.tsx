import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Calendar, Loader2, Sparkles, Hash, Users, AlertTriangle, RefreshCw } from 'lucide-react';
import { useDocumentStore, useNotificationStore } from '../store';
import TagCloud from '../components/knowledge/TagCloud';
import EntityPanel from '../components/knowledge/EntityPanel';
import ChangeReview from '../components/changes/ChangeReview';
import MarkdownRenderer from '../components/knowledge/MarkdownRenderer';
import { fetchChangeLogs } from '../services/api';
import api from '../services/api';
import { showToast } from '../components/common/Toast';
import type { ChangeLog } from '../types';

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { selectedDoc, isLoading, fetchDocument, clearSelected } = useDocumentStore();
  const fetchAlerts = useNotificationStore((s) => s.fetchAlerts);
  const [activeTab, setActiveTab] = useState<'preview' | 'raw' | 'knowledge'>('preview');
  const [changes, setChanges] = useState<ChangeLog[]>([]);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    if (id) { fetchDocument(id); loadChanges(); }
    return () => clearSelected();
  }, [id]);

  async function loadChanges() {
    if (!id) return;
    try { const data = await fetchChangeLogs({ document_id: id }); setChanges(data.items?.filter((c: ChangeLog) => !c.is_confirmed) || []); } catch {}
  }

  const handleReAnalyze = async () => {
    if (!id) return;
    setAiLoading(true);
    try {
      await api.post(`/organize/${id}`);
      showToast('success', 'AI分析已触发', '等待10-20秒后刷新查看结果');
      setTimeout(() => { fetchDocument(id); loadChanges(); setAiLoading(false); }, 3000);
    } catch (err: any) {
      showToast('error', 'AI分析失败', err.message);
      setAiLoading(false);
    }
  };

  if (isLoading || !selectedDoc) {
    return <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-primary-400" /></div>;
  }

  const doc = selectedDoc;
  let keywords: string[] = [];
  try { if ((doc as any).keywords) { keywords = typeof (doc as any).keywords === 'string' ? JSON.parse((doc as any).keywords) : (doc as any).keywords || []; } } catch {}

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-gray-200 transition-all"><ArrowLeft size={16} /> 返回列表</button>

      {changes.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-amber-400"><AlertTriangle size={16} /><span className="text-sm font-medium">待确认变更</span></div>
          {changes.map((c) => <ChangeReview key={c.id} change={c} onResolved={() => { loadChanges(); fetchAlerts(); }} />)}
        </div>
      )}

      <div className="glass-panel p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-white break-words">{doc.title}</h1>
            <div className="flex items-center gap-4 mt-3 text-sm text-gray-400">
              <span className="flex items-center gap-1"><FileText size={14} />{({ text:'文本',markdown:'MD',pdf:'PDF',image:'图片',url:'网页',note:'笔记' } as any)[doc.content_type]||doc.content_type}</span>
              <span className="flex items-center gap-1"><Calendar size={14} />{doc.created_at?.slice(0,10)}</span>
              <span>{doc.word_count}字</span>
            </div>
          </div>
          {/* AI Re-analyze button */}
          <button onClick={handleReAnalyze} disabled={aiLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-600/15 border border-primary-500/30
                       text-primary-400 hover:bg-primary-600/25 transition-all disabled:opacity-50 text-sm font-medium">
            {aiLoading ? <Loader2 size={16} className="animate-spin"/> : <RefreshCw size={16}/>}
            AI 分析
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="glass-panel">
            <div className="flex border-b border-gray-800/50 px-6">
              {[{key:'preview' as const,label:'内容'},{key:'raw' as const,label:'原文'},{key:'knowledge' as const,label:'知识'}].map(tab => (
                <button key={tab.key} onClick={()=>setActiveTab(tab.key)} className={`px-4 py-3 text-sm font-medium border-b-2 transition-all ${activeTab===tab.key?'border-primary-500 text-primary-400':'border-transparent text-gray-500 hover:text-gray-300'}`}>{tab.label}</button>
              ))}
            </div>
            <div className="p-6">
              {activeTab==='preview' && (doc.content_type==='markdown' ? <MarkdownRenderer content={doc.raw_text||''}/> : <pre className="whitespace-pre-wrap font-sans text-gray-300 leading-relaxed bg-transparent text-sm">{doc.raw_text||'(无内容)'}</pre>)}
              {activeTab==='raw' && <pre className="whitespace-pre-wrap font-mono text-gray-400 text-sm max-h-[70vh] overflow-y-auto">{doc.raw_text||'(无内容)'}</pre>}
              {activeTab==='knowledge' && (
                <div className="space-y-6">
                  {keywords.length>0 && <div><h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2"><Hash size={14}/>关键词</h3><TagCloud tags={keywords.map(k=>({name:k}))} size="sm" onTagClick={tag=>navigate(`/search?q=${encodeURIComponent(tag)}`)}/></div>}
                  {keywords.length===0 && <div className="text-center py-8"><Sparkles size={32} className="mx-auto mb-3 text-gray-600"/><p className="text-gray-500 text-sm">暂无知识数据</p><p className="text-gray-600 text-xs mt-1">点击右上角"AI分析"按钮进行智能分析</p></div>}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {/* AI Summary */}
          {(doc as any).summary ? (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2 mb-3"><Sparkles size={14} className="text-primary-400"/>AI 摘要</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                {(() => { try { const s = JSON.parse((doc as any).summary); return s.one_liner || s.summary || String(s); } catch { return (doc as any).summary; } })()}
              </p>
            </div>
          ) : (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2 mb-2"><Sparkles size={14} className="text-gray-600"/>AI 摘要</h3>
              <p className="text-xs text-gray-600">点击右上角"AI分析"按钮生成摘要</p>
              <button onClick={handleReAnalyze} disabled={aiLoading} className="btn-primary w-full mt-3 text-xs py-2">
                {aiLoading ? <Loader2 size={12} className="animate-spin inline mr-1"/> : <RefreshCw size={12} className="inline mr-1"/>}立即分析
              </button>
            </div>
          )}
          {/* Doc info */}
          <div className="glass-panel p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-3">文档信息</h3>
            <div className="space-y-2 text-xs text-gray-500">
              <div className="flex justify-between"><span>类型</span><span>{doc.content_type}</span></div>
              <div className="flex justify-between"><span>字数</span><span>{doc.word_count}</span></div>
              <div className="flex justify-between"><span>创建</span><span>{doc.created_at?.slice(0,16)}</span></div>
              {(doc as any).last_analyzed_at && <div className="flex justify-between"><span>AI分析</span><span>{(doc as any).last_analyzed_at?.slice(0,16)}</span></div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
