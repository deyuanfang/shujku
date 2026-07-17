import { useState, useEffect, useRef } from 'react';
import { PenLine, X, Send, Loader2 } from 'lucide-react';
import { uploadNote } from '../../services/api';
import { showToast } from '../common/Toast';

export default function QuickCapture() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Listen for global shortcut
  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'N') {
        e.preventDefault();
        setOpen(true);
      }
    });
    // Electron IPC
    if ((window as any).electronAPI?.onQuickNote) {
      (window as any).electronAPI.onQuickNote(() => setOpen(true));
    }
    return () => window.removeEventListener('keydown', handler as any);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      const result = await uploadNote(text.trim());
      if (result.status === 'ok') {
        showToast('success', '笔记已保存', `${result.category} · ${result.keywords.slice(0, 3).join(', ')}`);
        setText('');
        setOpen(false);
      }
    } catch (err: any) {
      showToast('error', '保存失败', err.message);
    }
    setSending(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit();
    }
    if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <>
      {/* Floating button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 w-12 h-12 rounded-full bg-primary-600 hover:bg-primary-500
                     shadow-lg shadow-primary-600/30 hover:shadow-primary-600/50
                     flex items-center justify-center transition-all hover:scale-110 active:scale-95"
          title="快速笔记 (Ctrl+Shift+N)"
        >
          <PenLine size={20} className="text-white" />
        </button>
      )}

      {/* Capture panel */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/60 backdrop-blur-sm animate-fade-in"
             onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
          <div className="w-full max-w-lg mx-4 glass-panel animate-slide-up overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/50">
              <span className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <PenLine size={15} className="text-primary-400" />
                快速笔记
              </span>
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-gray-600 mr-2">Ctrl+Enter 保存</span>
                <button onClick={() => setOpen(false)} className="btn-ghost p-1.5">
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Input */}
            <textarea
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="在这里写下你的想法、灵感、知识碎片..."
              rows={6}
              className="w-full bg-transparent text-gray-200 placeholder-gray-600 px-4 py-4 resize-none
                         focus:outline-none text-sm leading-relaxed"
              autoFocus
            />

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800/50 bg-gray-900/50">
              <span className="text-[10px] text-gray-600">
                {text.length} 字 · 自动分类并提取关键词
              </span>
              <button
                onClick={handleSubmit}
                disabled={!text.trim() || sending}
                className="btn-primary py-1.5 px-4 text-sm flex items-center gap-2"
              >
                {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                保存笔记
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
