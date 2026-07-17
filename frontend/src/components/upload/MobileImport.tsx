import { useState, useEffect, useRef } from 'react';
import { QrCode, Smartphone, Copy, RefreshCw, X, Wifi,Loader2 } from 'lucide-react';
import api from '../../services/api';
import { showToast } from '../common/Toast';

export default function MobileImportPanel() {
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [importCount, setImportCount] = useState(0);
  const pollRef = useRef<any>(null);

  useEffect(() => {
    if (open && session) {
      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get(`/mobile/session/${session.session_id}`);
          if (data.import_count !== undefined) {
            setImportCount(data.import_count);
          }
        } catch {}
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, session]);

  const createSession = async () => {
    setLoading(true);
    try {
      const { data } = await api.post('/mobile/session');
      setSession(data);
      setImportCount(0);
    } catch (err: any) {
      showToast('error', '创建会话失败', err.message);
    }
    setLoading(false);
  };

  const copyUrl = () => {
    if (session?.url) {
      navigator.clipboard.writeText(session.url);
      showToast('success', '链接已复制', '可发送到手机浏览器打开');
    }
  };

  const closePanel = () => {
    setOpen(false);
    setSession(null);
  };

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => { setOpen(true); createSession(); }}
        className="fixed bottom-20 right-6 z-40 w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-purple-600
                   hover:from-violet-400 hover:to-purple-500 shadow-lg shadow-purple-600/30
                   flex items-center justify-center transition-all hover:scale-110 active:scale-95"
        title="手机导入 (扫描二维码)"
      >
        <Smartphone size={20} className="text-white" />
      </button>

      {/* Panel */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in"
             onClick={(e) => { if (e.target === e.currentTarget) closePanel(); }}>
          <div className="w-full max-w-md mx-4 glass-panel animate-slide-up overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/50">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Smartphone size={20} className="text-violet-400" /> 手机导入
              </h2>
              <button onClick={closePanel} className="btn-ghost p-1.5"><X size={18} /></button>
            </div>

            <div className="p-6 space-y-5">
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={32} className="animate-spin text-primary-400" />
                </div>
              ) : session ? (
                <>
                  {/* QR Code */}
                  <div className="flex justify-center">
                    {session.qr_code ? (
                      <div className="bg-white p-3 rounded-xl">
                        <img
                          src={`data:image/png;base64,${session.qr_code}`}
                          alt="QR Code"
                          className="w-52 h-52"
                        />
                      </div>
                    ) : (
                      <div className="w-52 h-52 bg-gray-800 rounded-xl flex items-center justify-center">
                        <QrCode size={64} className="text-gray-600" />
                      </div>
                    )}
                  </div>

                  <p className="text-center text-sm text-gray-400">
                    用手机扫描二维码，即可从手机导入知识
                  </p>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button onClick={copyUrl} className="btn-secondary flex-1 text-sm py-2 flex items-center justify-center gap-2">
                      <Copy size={14} /> 复制链接
                    </button>
                    <button onClick={createSession} className="btn-ghost flex-1 text-sm py-2 flex items-center justify-center gap-2">
                      <RefreshCw size={14} /> 刷新
                    </button>
                  </div>

                  {/* Stats */}
                  <div className="flex gap-3 text-center">
                    <div className="flex-1 bg-gray-800/50 rounded-xl p-3">
                      <p className="text-2xl font-bold text-violet-400">{importCount}</p>
                      <p className="text-[10px] text-gray-500">本次导入</p>
                    </div>
                    <div className="flex-1 bg-gray-800/50 rounded-xl p-3">
                      <p className="text-[10px] text-gray-500 mt-2">同一 WiFi</p>
                      <div className="flex items-center justify-center gap-1 text-emerald-400">
                        <Wifi size={12} /> <span className="text-xs">局域网</span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8">
                  <QrCode size={48} className="mx-auto mb-3 text-gray-600" />
                  <p className="text-gray-400">生成失败</p>
                  <button onClick={createSession} className="btn-primary mt-3 text-sm">重试</button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
