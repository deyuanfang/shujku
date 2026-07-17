import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, FileText, Calendar, Loader2, Sparkles,
  Hash, Users, AlertTriangle,
} from 'lucide-react';
import { useDocumentStore, useNotificationStore } from '../store';
import TagCloud from '../components/knowledge/TagCloud';
import EntityPanel from '../components/knowledge/EntityPanel';
import ChangeReview from '../components/changes/ChangeReview';
import MarkdownRenderer from '../components/knowledge/MarkdownRenderer';
import QuickCapture from '../components/upload/QuickCapture';
import { fetchChangeLogs } from '../services/api';
import type { ChangeLog } from '../types';

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { selectedDoc, isLoading, fetchDocument, clearSelected } = useDocumentStore();
  const fetchAlerts = useNotificationStore((s) => s.fetchAlerts);
  const [activeTab, setActiveTab] = useState<'preview' | 'raw' | 'knowledge'>('preview');
  const [changes, setChanges] = useState<ChangeLog[]>([]);

  useEffect(() => {
    if (id) {
      fetchDocument(id);
      fetchChangeLogs({ document_id: id }).then((data) => {
        setChanges(data.items?.filter((c: ChangeLog) => !c.is_confirmed) || []);
      });
    }
    return () => clearSelected();
  }, [id]);

  const handleChangeResolved = () => {
    if (id) {
      fetchChangeLogs({ document_id: id }).then((data) => {
        setChanges(data.items?.filter((c: ChangeLog) => !c.is_confirmed) || []);
      });
      fetchAlerts();
    }
  };

  if (isLoading || !selectedDoc) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-primary-400" />
      </div>
    );
  }

  const doc = selectedDoc;

  // Parse keywords/entities if available
  let keywords: string[] = [];
  let entities: Array<{ name: string; type: string; description?: string }> = [];
  try {
    if ((doc as any).keywords) {
      keywords = typeof (doc as any).keywords === 'string'
        ? JSON.parse((doc as any).keywords)
        : (doc as any).keywords || [];
    }
  } catch {}

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* Back */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-gray-400 hover:text-gray-200 transition-all">
        <ArrowLeft size={16} /> 返回列表
      </button>

      {/* Pending change reviews */}
      {changes.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-amber-400">
            <AlertTriangle size={16} />
            <span className="text-sm font-medium">有待确认的变更</span>
          </div>
          {changes.map((change) => (
            <ChangeReview key={change.id} change={change} onResolved={handleChangeResolved} />
          ))}
        </div>
      )}

      {/* Document header */}
      <div className="glass-panel p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-white break-words">{doc.title}</h1>
            <div className="flex items-center gap-4 mt-3 text-sm text-gray-400">
              <span className="flex items-center gap-1">
                <FileText size={14} />
                {({ text: '文本', markdown: 'Markdown', pdf: 'PDF', image: '图片', url: '网页', note: '笔记' } as any)[doc.content_type] || doc.content_type}
              </span>
              <span className="flex items-center gap-1">
                <Calendar size={14} /> {doc.created_at?.slice(0, 10)}
              </span>
              <span>{doc.word_count} 字 · {doc.char_count} 字符</span>
              <span className="flex items-center gap-1">
                <Sparkles size={14} className="text-primary-400" />
                {(doc as any).importance ? `${((doc as any).importance * 100).toFixed(0)}%` : 'N/A'}
              </span>
            </div>
          </div>
        </div>
        {doc.source_url && (
          <a href={doc.source_url} target="_blank" rel="noopener noreferrer"
             className="text-sm text-primary-400 hover:text-primary-300 break-all">
            来源: {doc.source_url}
          </a>
        )}
      </div>

      {/* Content + Knowledge side panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2">
          <div className="glass-panel">
            <div className="flex border-b border-gray-800/50 px-6">
              {[
                { key: 'preview' as const, label: '内容' },
                { key: 'raw' as const, label: '原文' },
                { key: 'knowledge' as const, label: '知识' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-all ${
                    activeTab === tab.key
                      ? 'border-primary-500 text-primary-400'
                      : 'border-transparent text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-6">
              {activeTab === 'preview' && (
                doc.content_type === 'markdown' ? (
                  <MarkdownRenderer content={doc.raw_text || ''} />
                ) : (
                  <pre className="whitespace-pre-wrap font-sans text-gray-300 leading-relaxed bg-transparent text-sm">
                    {doc.raw_text || '（无文本内容）'}
                  </pre>
                )
              )}
              {activeTab === 'raw' && (
                <pre className="whitespace-pre-wrap font-mono text-gray-400 text-sm max-h-[70vh] overflow-y-auto">
                  {doc.raw_text || '（无文本内容）'}
                </pre>
              )}
              {activeTab === 'knowledge' && (
                <div className="space-y-6">
                  {keywords.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                        <Hash size={14} /> 关键词
                      </h3>
                      <TagCloud
                        tags={keywords.map((k) => ({ name: k }))}
                        size="sm"
                        onTagClick={(tag) => navigate(`/search?q=${encodeURIComponent(tag)}`)}
                      />
                    </div>
                  )}
                  {entities.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                        <Users size={14} /> 相关实体
                      </h3>
                      <EntityPanel entities={entities} />
                    </div>
                  )}
                  {keywords.length === 0 && entities.length === 0 && (
                    <div className="text-center py-8">
                      <Sparkles size={32} className="mx-auto mb-3 text-gray-600" />
                      <p className="text-gray-500 text-sm">AI 分析尚未完成</p>
                      <p className="text-gray-600 text-xs mt-1">
                        配置 Claude API Key 后，上传内容将自动提取关键词和实体
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Side panel: Summary + Tags + Entities */}
        <div className="space-y-4">
          {/* AI Summary */}
          {(doc as any).summary ? (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-primary-400" /> AI 摘要
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed">{(doc as any).summary}</p>
            </div>
          ) : (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-gray-600" /> AI 摘要
              </h3>
              <p className="text-xs text-gray-600">
                配置 API Key 后自动生成。在设置页面添加 Claude API Key。
              </p>
            </div>
          )}

          {/* Keywords */}
          {keywords.length > 0 && (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 mb-3">关键词</h3>
              <TagCloud
                tags={keywords.map((k) => ({ name: k }))}
                size="sm"
                onTagClick={(tag) => navigate(`/search?q=${encodeURIComponent(tag)}`)}
              />
            </div>
          )}

          {/* Entities */}
          {entities.length > 0 && (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 mb-3">
                实体 ({entities.length})
              </h3>
              <EntityPanel entities={entities.slice(0, 8)} />
              {entities.length > 8 && (
                <p className="text-xs text-gray-600 mt-2">还有 {entities.length - 8} 个实体</p>
              )}
            </div>
          )}

          {/* Document info */}
          <div className="glass-panel p-4">
            <h3 className="text-sm font-medium text-gray-300 mb-3">文档信息</h3>
            <div className="space-y-2 text-xs text-gray-500">
              <div className="flex justify-between">
                <span>类型</span>
                <span>{doc.content_type}</span>
              </div>
              <div className="flex justify-between">
                <span>字数</span>
                <span>{doc.word_count}</span>
              </div>
              <div className="flex justify-between">
                <span>创建时间</span>
                <span>{doc.created_at?.slice(0, 16)}</span>
              </div>
              <div className="flex justify-between">
                <span>更新时间</span>
                <span>{doc.updated_at?.slice(0, 16)}</span>
              </div>
              <div className="flex justify-between">
                <span>内容哈希</span>
                <span className="font-mono text-[10px]">{doc.original_hash?.slice(0, 12)}...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
