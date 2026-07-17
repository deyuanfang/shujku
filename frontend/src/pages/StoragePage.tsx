import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  HardDrive, Server, Usb, Cloud, Search, RefreshCw,
  Download, FileText, Loader2, Wifi, WifiOff, AlertCircle,
} from 'lucide-react';
import api from '../services/api';
import { showToast } from '../components/common/Toast';

interface StorageInfo {
  id: string; name: string; type: string; status: string;
  icon: string; description: string;
  info?: Record<string, any>;
}

interface ScanResult {
  storage_id: string; total: number;
  files: Array<{ path: string; name: string; size_mb: number;
                 modified_at?: string; content_type: string; }>;
}

const ICON_MAP: Record<string, typeof HardDrive> = {
  'hard-drive': HardDrive, server: Server, usb: Usb, cloud: Cloud,
};

const TYPE_LABELS: Record<string, string> = {
  local: '本地存储', nas: '网络存储 (NAS)',
  removable: '移动存储', baidu_cloud: '百度网盘',
};

export default function StoragePage() {
  const navigate = useNavigate();
  const [storages, setStorages] = useState<StorageInfo[]>([]);
  const [scanning, setScanning] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadStorages(); }, []);

  async function loadStorages() {
    setLoading(true);
    try {
      const { data } = await api.get('/storage/list');
      setStorages(data);
    } catch { showToast('error', '无法加载存储列表'); }
    setLoading(false);
  }

  async function scanStorage(storageId: string) {
    setScanning(storageId);
    setSelectedFiles(new Set());
    try {
      const { data } = await api.post('/storage/scan', {
        storage_id: storageId, recursive: true,
      });
      setScanResult(data);
      showToast('success', `扫描完成`, `发现 ${data.total} 个文件`);
    } catch (err: any) {
      showToast('error', '扫描失败', err.message);
    }
    setScanning(null);
  }

  async function importSelected() {
    if (selectedFiles.size === 0) return;
    setImporting(true);
    try {
      const paths = Array.from(selectedFiles).join(',');
      const { data } = await api.post('/storage/import', null, {
        params: { storage_id: scanResult!.storage_id, file_paths: paths },
      });
      showToast('success', `导入完成`, `${data.imported} 篇, ${data.duplicates} 篇重复, ${data.errors} 个错误`);
      if (data.imported > 0) navigate('/documents');
    } catch (err: any) {
      showToast('error', '导入失败', err.message);
    }
    setImporting(false);
  }

  function toggleFile(path: string) {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }

  function selectAll() {
    if (!scanResult) return;
    setSelectedFiles(new Set(scanResult.files.map(f => f.path)));
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold text-white">存储管理</h1>

      {/* Storage list */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-primary-400" size={24}/></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {storages.map((s) => {
            const Icon = ICON_MAP[s.icon] || HardDrive;
            const isOnline = s.status === 'online';

            return (
              <div key={s.id} className={`glass-panel p-5 ${isOnline ? 'hover:border-gray-600' : 'opacity-60'}`}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      isOnline ? 'bg-primary-600/20' : 'bg-gray-700/50'
                    }`}>
                      <Icon size={20} className={isOnline ? 'text-primary-400' : 'text-gray-500'} />
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-200">{s.name}</h3>
                      <p className="text-xs text-gray-500">{TYPE_LABELS[s.type] || s.type}</p>
                    </div>
                  </div>
                  <span className={`badge text-[10px] ${isOnline ? 'badge-success' : 'badge-warning'}`}>
                    {isOnline ? <Wifi size={10} className="mr-1 inline"/> : <WifiOff size={10} className="mr-1 inline"/>}
                    {s.status === 'online' ? '可用' : s.status === 'not_configured' ? '未配置' : '离线'}
                  </span>
                </div>

                <p className="text-xs text-gray-600 mb-3">{s.description}</p>

                {s.info?.free_gb !== undefined && (
                  <div className="mb-3">
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>已用 {((s.info.total_gb || 0) - (s.info.free_gb || 0)).toFixed(0)} GB</span>
                      <span>{s.info.total_gb?.toFixed(0)} GB</span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full bg-primary-600 rounded-full"
                        style={{ width: `${s.info.total_gb ? ((1 - s.info.free_gb / s.info.total_gb) * 100) : 0}%` }}/>
                    </div>
                  </div>
                )}

                {isOnline && (
                  <button
                    onClick={() => scanStorage(s.id)}
                    disabled={scanning === s.id}
                    className="btn-secondary w-full text-sm py-2 flex items-center justify-center gap-2"
                  >
                    {scanning === s.id ? <Loader2 size={14} className="animate-spin"/> : <Search size={14}/>}
                    扫描文件
                  </button>
                )}

                {s.type === 'baidu_cloud' && s.status !== 'online' && (
                  <button className="btn-primary w-full text-sm py-2" onClick={async () => {
                    try {
                      const { data } = await api.get('/storage/cloud/auth-url?cloud_type=baidu');
                      if (data.auth_url) {
                        window.open(data.auth_url, '_blank');
                        showToast('info', '请在浏览器中完成百度网盘授权');
                      }
                    } catch { showToast('error', '获取授权链接失败'); }
                  }}>
                    连接百度网盘
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Scan results */}
      {scanResult && (
        <div className="glass-panel">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800/50">
            <h2 className="font-medium text-gray-200">
              扫描结果 ({scanResult.total} 个文件)
            </h2>
            <div className="flex gap-2">
              <button onClick={selectAll} className="btn-ghost text-xs">全选</button>
              <button
                onClick={importSelected}
                disabled={selectedFiles.size === 0 || importing}
                className="btn-primary text-sm py-1.5 px-4 flex items-center gap-2"
              >
                {importing ? <Loader2 size={14} className="animate-spin"/> : <Download size={14}/>}
                导入选中 ({selectedFiles.size})
              </button>
            </div>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {scanResult.files.length === 0 ? (
              <p className="text-center text-gray-500 py-12">未发现支持的文件类型</p>
            ) : (
              scanResult.files.map((f) => (
                <div
                  key={f.path}
                  onClick={() => toggleFile(f.path)}
                  className={`flex items-center gap-3 px-5 py-2.5 border-b border-gray-800/30 cursor-pointer transition-all
                    ${selectedFiles.has(f.path) ? 'bg-primary-600/10' : 'hover:bg-gray-800/30'}`}
                >
                  <input type="checkbox" checked={selectedFiles.has(f.path)} readOnly
                    className="w-4 h-4 rounded accent-primary-600"/>
                  <FileText size={14} className="text-gray-500 flex-shrink-0"/>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-200 truncate">{f.name}</p>
                    <p className="text-xs text-gray-600 truncate">{f.path}</p>
                  </div>
                  <span className="text-xs text-gray-500">{f.size_mb.toFixed(1)} MB</span>
                  <span className="badge badge-primary text-[10px]">{f.content_type}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
