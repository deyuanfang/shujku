import { useState, useCallback } from 'react';
import { X, Upload, Link, Pencil, FileText, Loader2 } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { useUIStore, useDocumentStore } from '../../store';
import { uploadFile, uploadURL, uploadNote } from '../../services/api';

type TabType = 'file' | 'url' | 'note';

export default function UploadModal() {
  const closeUpload = useUIStore((s) => s.closeUpload);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const [activeTab, setActiveTab] = useState<TabType>('file');
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);
    setError(null);
    try {
      for (const file of acceptedFiles) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await uploadFile(formData);
        setResult(res);
      }
      fetchDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const handleURLSubmit = async () => {
    if (!url.trim()) return;
    setUploading(true);
    setError(null);
    try {
      const res = await uploadURL(url.trim());
      setResult(res);
      fetchDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleNoteSubmit = async () => {
    if (!note.trim()) return;
    setUploading(true);
    setError(null);
    try {
      const res = await uploadNote(note.trim(), noteTitle.trim() || undefined);
      setResult(res);
      fetchDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setUploading(false);
    }
  };

  const tabs: { key: TabType; icon: any; label: string }[] = [
    { key: 'file', icon: Upload, label: '文件上传' },
    { key: 'url', icon: Link, label: '网页链接' },
    { key: 'note', icon: Pencil, label: '快速笔记' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass-panel w-full max-w-lg mx-4 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800/50">
          <h2 className="text-lg font-semibold text-white">添加新内容</h2>
          <button onClick={closeUpload} className="btn-ghost p-1">
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-800/50">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setResult(null); setError(null); }}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-all border-b-2
                ${activeTab === tab.key
                  ? 'border-primary-500 text-primary-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
                }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6">
          {activeTab === 'file' && (
            <div
              {...getRootProps()}
              className={`
                border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all
                ${isDragActive
                  ? 'border-primary-500 bg-primary-600/10'
                  : 'border-gray-700 hover:border-gray-500'
                }
              `}
            >
              <input {...getInputProps()} />
              <Upload size={40} className="mx-auto mb-3 text-gray-500" />
              <p className="text-gray-300 font-medium">拖拽文件到此处，或点击选择</p>
              <p className="text-sm text-gray-500 mt-1">
                支持 TXT、Markdown、PDF、图片 (最大 50MB)
              </p>
            </div>
          )}

          {activeTab === 'url' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">网页链接</label>
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/article"
                  className="input-field"
                />
              </div>
              <button
                onClick={handleURLSubmit}
                disabled={!url.trim() || uploading}
                className="btn-primary w-full"
              >
                {uploading ? <Loader2 size={16} className="animate-spin inline mr-2" /> : null}
                抓取并分析
              </button>
            </div>
          )}

          {activeTab === 'note' && (
            <div className="space-y-4">
              <input
                type="text"
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
                placeholder="笔记标题（可选）"
                className="input-field"
              />
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="在这里写下你的想法、灵感、知识碎片..."
                rows={6}
                className="input-field resize-none"
              />
              <button
                onClick={handleNoteSubmit}
                disabled={!note.trim() || uploading}
                className="btn-primary w-full"
              >
                {uploading ? <Loader2 size={16} className="animate-spin inline mr-2" /> : null}
                保存笔记
              </button>
            </div>
          )}

          {/* Upload progress / result */}
          {uploading && (
            <div className="mt-4 flex items-center gap-3 text-sm text-gray-400">
              <Loader2 size={16} className="animate-spin" />
              正在处理中...
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-600/10 border border-red-600/30 rounded-lg text-sm text-red-400">
              {error}
            </div>
          )}

          {result && result.status === 'duplicate' && (
            <div className="mt-4 p-3 bg-amber-600/10 border border-amber-600/30 rounded-lg text-sm text-amber-400">
              {result.message}
            </div>
          )}

          {result && result.status === 'ok' && (
            <div className="mt-4 p-4 bg-emerald-600/10 border border-emerald-600/30 rounded-lg">
              <p className="text-emerald-400 font-medium text-sm mb-2">✓ 内容已成功添加</p>
              <p className="text-gray-300 text-sm">标题: {result.title}</p>
              <p className="text-gray-400 text-sm">
                分类: {result.category}
                {result.confidence > 0 && ` (置信度: ${(result.confidence * 100).toFixed(0)}%)`}
              </p>
              {result.keywords?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {result.keywords.map((kw: string) => (
                    <span key={kw} className="badge badge-primary">{kw}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
