import { useState } from 'react';
import { Search, FolderOpen, Trash2, Scissors, Copy, ArrowRight, Loader2, Shield, HardDrive } from 'lucide-react';
import api from '../services/api';
import { showToast } from '../components/common/Toast';

export default function FileManagerPage() {
  const [path, setPath] = useState('C:\\Users\\11921\\Desktop');
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [organizing, setOrganizing] = useState(false);
  const [deduping, setDeduping] = useState(false);
  const [tab, setTab] = useState<'scan' | 'dedup'>('scan');

  async function handleScan(deep = false) {
    setScanning(true);
    try {
      const { data } = await api.post('/files/scan', { path, recursive: true, deep });
      setResult(data);
      if (data.total_files > 0) {
        showToast('success', `扫描完成`, `${data.total_files} 个文件, ${data.total_size_mb} MB`);
        if (data.duplicate_groups > 0) showToast('warning', `发现 ${data.duplicate_groups} 组重复文件`, `浪费 ${data.wasted_mb} MB`);
      } else showToast('warning', '未发现文件');
    } catch (e: any) { showToast('error', '扫描失败', e.message); }
    setScanning(false);
  }

  async function handleOrganize(strategy = 'category', action = 'copy', dryRun = true) {
    setOrganizing(true);
    try {
      const { data } = await api.post('/files/organize', { path, strategy, action, dry_run: dryRun });
      showToast('success', dryRun ? `预览: ${data.files_to_organize} 个文件` : `已${action === 'move' ? '移动' : '复制'} ${data.files_to_organize} 个文件`);
      setResult((prev: any) => ({ ...prev, organize_plan: data }));
    } catch (e: any) { showToast('error', '整理失败', e.message); }
    setOrganizing(false);
  }

  async function handleDedup(execute = false) {
    if (execute && !confirm('确定要删除所有重复文件？此操作不可撤销！')) return;
    setDeduping(true);
    try {
      const { data } = await api.post('/files/dedup', null, { params: { path, dry_run: !execute } });
      showToast('success', execute ? `已释放 ${data.freed_mb} MB` : `预览: 可释放 ${data.freed_mb} MB，${data.duplicate_files} 个重复文件`);
    } catch (e: any) { showToast('error', '操作失败', e.message); }
    setDeduping(false);
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5 animate-fade-in">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2"><HardDrive size={22} className="text-primary-400" /> 本地文件管理</h1>

      {/* Path input */}
      <div className="glass-panel p-4 flex gap-3">
        <FolderOpen size={18} className="text-gray-500 mt-2 flex-shrink-0" />
        <input value={path} onChange={e => setPath(e.target.value)}
          placeholder="输入文件夹路径 (如 C:\Users\...)" className="input-field flex-1 text-sm" />
        <button onClick={() => handleScan(false)} disabled={scanning} className="btn-primary text-sm px-4 flex items-center gap-2">
          {scanning ? <Loader2 size={14} className="animate-spin"/> : <Search size={14}/>} 快速扫描
        </button>
        <button onClick={() => handleScan(true)} disabled={scanning} className="btn-secondary text-sm px-4 flex items-center gap-2">
          {scanning ? <Loader2 size={14} className="animate-spin"/> : <Shield size={14}/>} 深度扫描(Hash)
        </button>
      </div>

      {/* Tabs */}
      {result && (
        <>
          <div className="flex gap-2">
            {[{key:'scan',label:'文件概览'},{key:'dedup',label:'重复文件'}].map(t => (
              <button key={t.key} onClick={() => setTab(t.key as any)}
                className={`px-4 py-1.5 text-sm rounded-lg ${tab === t.key ? 'bg-primary-600/20 text-primary-400' : 'text-gray-500'}`}>{t.label}</button>
            ))}
          </div>

          {tab === 'scan' && (
            <>
              {/* Stats */}
              <div className="grid grid-cols-4 gap-3">
                {[{label:'文件总数',v:result.total_files},{label:'总大小',v:result.total_size_mb+' MB'},{label:'重复组',v:result.duplicate_groups},{label:'浪费空间',v:result.wasted_mb+' MB'}].map(s => (
                  <div key={s.label} className="glass-panel p-3 text-center">
                    <p className="text-xl font-bold text-white">{s.v}</p><p className="text-[10px] text-gray-500">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Categories */}
              <div className="glass-panel p-4">
                <h3 className="text-sm font-medium text-gray-300 mb-3">文件类型分布</h3>
                <div className="space-y-2">
                  {result.by_category && Object.entries(result.by_category).map(([cat, count]: any) => (
                    <div key={cat} className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 w-16">{cat}</span>
                      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-primary-600 rounded-full" style={{width:`${Math.max(2,count/result.total_files*100)}%`}}/>
                      </div>
                      <span className="text-xs text-gray-500 w-8 text-right">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Organize actions */}
              <div className="glass-panel p-4">
                <h3 className="text-sm font-medium text-gray-300 mb-3">整理操作</h3>
                <div className="flex gap-2 flex-wrap">
                  <button onClick={() => handleOrganize('category','copy',true)} disabled={organizing} className="btn-secondary text-xs py-1.5 px-3">📋 预览(按类型分组)</button>
                  <button onClick={() => handleOrganize('date','copy',true)} disabled={organizing} className="btn-secondary text-xs py-1.5 px-3">📅 预览(按日期分组)</button>
                  <button onClick={() => handleOrganize('category','move',false)} disabled={organizing} className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1"><Scissors size={12}/> 执行移动</button>
                  <button onClick={() => handleOrganize('category','copy',false)} disabled={organizing} className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1"><Copy size={12}/> 执行复制</button>
                </div>
                {result.organize_plan && (
                  <div className="mt-3 p-3 bg-gray-800/30 rounded-lg text-xs text-gray-400">
                    {result.organize_plan.dry_run ? '预览模式' : '已执行'}：{result.organize_plan.files_to_organize} 文件 → {result.organize_plan.folders_to_create} 个文件夹
                  </div>
                )}
              </div>
            </>
          )}

          {tab === 'dedup' && (
            <div className="glass-panel p-4">
              <h3 className="text-sm font-medium text-gray-300 mb-3">重复文件 ({result.duplicate_groups} 组)</h3>
              {result.duplicates?.length > 0 ? (
                <>
                  {result.duplicates.slice(0, 10).map((g: any, i: number) => (
                    <div key={i} className="mb-3 p-3 bg-gray-800/20 rounded-lg">
                      <p className="text-xs text-gray-500 mb-1">Hash: {g.hash}... | {g.count}个副本 | 浪费 {g.wasted_kb} KB</p>
                      {g.files?.map((f: any) => (
                        <p key={f.path} className="text-xs text-gray-400 truncate pl-3">📄 {f.name} ({f.size_kb}KB)</p>
                      ))}
                    </div>
                  ))}
                  <div className="flex gap-2 mt-4">
                    <button onClick={() => handleDedup(false)} disabled={deduping} className="btn-secondary text-sm py-1.5 px-4">预览删除</button>
                    <button onClick={() => handleDedup(true)} disabled={deduping} className="btn-primary text-sm py-1.5 px-4 flex items-center gap-1">
                      <Trash2 size={14}/> 执行删除重复文件
                    </button>
                  </div>
                </>
              ) : (
                <p className="text-gray-500 text-sm py-4 text-center">未发现重复文件（需要深度扫描）</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
