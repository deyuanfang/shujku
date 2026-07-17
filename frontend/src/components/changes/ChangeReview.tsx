import { useState } from 'react';
import { AlertTriangle, Check, X, ChevronDown, ChevronUp } from 'lucide-react';
import type { ChangeLog } from '../../types';
import { confirmChange, dismissChange } from '../../services/api';

interface Props {
  change: ChangeLog;
  onResolved: () => void;
}

export default function ChangeReview({ change, onResolved }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resolved, setResolved] = useState(false);

  const severityConfig = {
    minor: { color: 'text-gray-400', bg: 'bg-gray-600/10', label: '轻微' },
    moderate: { color: 'text-emerald-400', bg: 'bg-emerald-600/10', label: '一般' },
    significant: { color: 'text-amber-400', bg: 'bg-amber-600/10', label: '显著' },
    major: { color: 'text-red-400', bg: 'bg-red-600/10', label: '重大' },
  };

  const config = severityConfig[change.severity_label] || severityConfig.minor;

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await confirmChange(change.id);
      setResolved(true);
      onResolved();
    } catch { setLoading(false); }
  };

  const handleDismiss = async () => {
    setLoading(true);
    try {
      await dismissChange(change.id);
      setResolved(true);
      onResolved();
    } catch { setLoading(false); }
  };

  if (resolved) return null;

  return (
    <div className={`glass-panel border ${change.severity_label === 'major' ? 'border-red-600/30' : 'border-amber-600/20'}`}>
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-800/30 transition-all"
        onClick={() => setExpanded(!expanded)}
      >
        <AlertTriangle size={18} className={config.color} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200">
            文档内容变更
            <span className={`ml-2 badge text-[10px] ${config.color} ${config.bg}`}>
              {config.label}
            </span>
          </p>
          <p className="text-xs text-gray-500 mt-0.5">{change.content_diff || change.created_at}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); handleConfirm(); }}
            disabled={loading}
            className="btn-primary py-1.5 px-3 text-xs"
          >
            <Check size={14} className="mr-1 inline" />确认
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
            disabled={loading}
            className="btn-secondary py-1.5 px-3 text-xs"
          >
            <X size={14} className="mr-1 inline" />忽略
          </button>
          {expanded ? <ChevronUp size={16} className="text-gray-500" /> : <ChevronDown size={16} className="text-gray-500" />}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-800/50 pt-3 space-y-3">
          {change.content_diff && (
            <div>
              <p className="text-xs text-gray-500 mb-1">变更摘要</p>
              <p className="text-sm text-gray-300">{change.content_diff}</p>
            </div>
          )}
          {change.entity_changes && (
            <div>
              <p className="text-xs text-gray-500 mb-1">关键词变化</p>
              <pre className="text-xs text-gray-400 whitespace-pre-wrap font-mono bg-gray-900/50 p-2 rounded">
                {(() => {
                  try {
                    const parsed = JSON.parse(change.entity_changes);
                    let text = '';
                    if (parsed.added_keywords?.length) text += `+新增: ${parsed.added_keywords.join(', ')}\n`;
                    if (parsed.removed_keywords?.length) text += `-移除: ${parsed.removed_keywords.join(', ')}`;
                    return text || '无显著变化';
                  } catch { return change.entity_changes; }
                })()}
              </pre>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>严重程度评分: {(change.severity * 100).toFixed(0)}%</span>
            <span>·</span>
            <span>{change.created_at?.slice(0, 16)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
