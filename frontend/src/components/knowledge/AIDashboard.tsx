import { useEffect, useState, useRef } from 'react';
import { Cpu, Sparkles, Zap, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import api from '../../services/api';

interface AIStats { total_actions: number; success: number; failed: number; total_tokens: number; }
interface AILog { id: string; status: string; action_type: string; provider: string; model: string; duration_ms: number; result_summary?: string; error_message?: string; created_at: string; }

const ACTION_LABELS: Record<string, string> = { analyze: '分析文档', summarize: '生成摘要', extract_entities: '提取实体', organize: '整理分类', insights: '洞察分析' };

export default function AIDashboard() {
  const [stats, setStats] = useState<AIStats | null>(null);
  const [logs, setLogs] = useState<AILog[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const pollRef = useRef<any>(null);

  useEffect(() => {
    fetchData();
    pollRef.current = setInterval(fetchData, 5000);
    return () => clearInterval(pollRef.current);
  }, []);

  async function fetchData() {
    try {
      const [statsR, logsR] = await Promise.all([
        api.get('/monitor/ai-logs/stats'),
        api.get('/monitor/ai-logs?limit=10'),
      ]);
      setStats(statsR.data);
      setLogs(logsR.data.logs || []);
    } catch {}
    setLoading(false);
  }

  const runningCount = logs.filter(l => l.status === 'running').length;
  const latestLog = logs[0];

  if (!expanded) {
    return (
      <button onClick={() => setExpanded(true)}
        className="fixed bottom-28 right-6 z-40 px-3 py-2 rounded-full bg-gray-900/90 border border-gray-700/50
                   hover:border-primary-500/50 transition-all flex items-center gap-2 shadow-lg text-xs">
        <Sparkles size={14} className={runningCount > 0 ? 'text-primary-400 animate-pulse' : 'text-gray-500'} />
        <span className="text-gray-400">AI {stats ? `${stats.total_actions}次` : '...'}</span>
        {runningCount > 0 && <span className="w-2 h-2 rounded-full bg-primary-400 animate-pulse"/>}
      </button>
    );
  }

  return (
    <div className="fixed bottom-28 right-6 z-40 w-80 glass-panel animate-slide-up max-h-96 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/50">
        <h3 className="text-sm font-medium text-white flex items-center gap-2">
          <Cpu size={14} className="text-primary-400" /> AI 运行状态
        </h3>
        <button onClick={() => setExpanded(false)} className="text-gray-500 hover:text-gray-300 text-lg leading-none">&times;</button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-2 px-4 py-3 border-b border-gray-800/30">
          {[
            { label: '总计', value: stats.total_actions, color: 'text-gray-300' },
            { label: '成功', value: stats.success, color: 'text-emerald-400' },
            { label: '失败', value: stats.failed, color: 'text-red-400' },
            { label: 'Token', value: stats.total_tokens > 1000 ? `${(stats.total_tokens/1000).toFixed(1)}k` : stats.total_tokens, color: 'text-primary-400' },
          ].map(s => (
            <div key={s.label} className="text-center">
              <p className={`text-lg font-bold ${s.color}`}>{s.value}</p>
              <p className="text-[9px] text-gray-600">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Logs */}
      <div className="max-h-48 overflow-y-auto px-2 py-2 space-y-1">
        {loading ? <Loader2 size={16} className="animate-spin mx-auto text-gray-600"/> :
         logs.length === 0 ? <p className="text-xs text-gray-600 text-center py-4">暂无 AI 调用记录</p> :
         logs.map(log => (
          <div key={log.id} className="flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-white/[0.03] text-xs">
            {log.status === 'success' ? <CheckCircle size={12} className="text-emerald-400 mt-0.5 flex-shrink-0"/> :
             log.status === 'failed' ? <XCircle size={12} className="text-red-400 mt-0.5 flex-shrink-0"/> :
             log.status === 'running' ? <Loader2 size={12} className="animate-spin text-primary-400 mt-0.5 flex-shrink-0"/> :
             <Clock size={12} className="text-gray-500 mt-0.5 flex-shrink-0"/>}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-gray-300 truncate">{ACTION_LABELS[log.action_type] || log.action_type}</span>
                <span className="text-[9px] text-gray-600">{log.provider}/{log.model}</span>
                <span className="text-[9px] text-gray-700 ml-auto">{log.duration_ms}ms</span>
              </div>
              {log.result_summary && <p className="text-[10px] text-gray-500 truncate">{log.result_summary}</p>}
              {log.error_message && <p className="text-[10px] text-red-400/70 truncate">{log.error_message}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
