import { useLocation, useNavigate } from 'react-router-dom';
import { ChevronRight, Home, ArrowLeft } from 'lucide-react';

const PAGE_NAMES: Record<string, string> = {
  '': '仪表盘',
  'documents': '文档',
  'graph': '知识图谱',
  'search': '搜索',
  'settings': '设置',
  'storage': '存储',
  'setup': '设置向导',
};

interface Props {
  showBack?: boolean;
  backTo?: string;
  backLabel?: string;
}

export default function Breadcrumb({ showBack = true, backTo, backLabel }: Props) {
  const location = useLocation();
  const navigate = useNavigate();

  const segments = location.pathname.split('/').filter(Boolean);
  const isHome = segments.length === 0;

  // Dynamic page name for document detail
  const getPageName = (seg: string, index: number) => {
    if (seg.length > 30) return seg.slice(0, 8) + '…'; // UUID
    if (index === 1 && segments[0] === 'documents') return '详情';
    return PAGE_NAMES[seg] || seg;
  };

  return (
    <div className="flex items-center gap-2 text-sm">
      {/* Back button */}
      {showBack && !isHome && (
        <button
          onClick={() => backTo ? navigate(backTo) : navigate(-1)}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-gray-400
                     hover:text-gray-200 hover:bg-white/[0.04] transition-all mr-1"
          title={backLabel || '返回'}
        >
          <ArrowLeft size={15} />
          <span className="text-xs hidden sm:inline">{backLabel || '返回'}</span>
        </button>
      )}

      {/* Home */}
      <button
        onClick={() => navigate('/')}
        className={`flex items-center gap-1 px-2 py-1 rounded-lg transition-all
          ${isHome ? 'text-primary-400 bg-primary-600/10' : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]'}`}
        title="首页"
      >
        <Home size={14} />
      </button>

      {/* Path segments */}
      {segments.map((seg, i) => (
        <span key={i} className="flex items-center gap-2">
          <ChevronRight size={12} className="text-gray-700" />
          <button
            onClick={() => {
              const path = '/' + segments.slice(0, i + 1).join('/');
              navigate(path);
            }}
            className={`px-2 py-1 rounded-lg transition-all truncate max-w-[200px]
              ${i === segments.length - 1
                ? 'text-gray-200 font-medium bg-white/[0.03]'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]'}`}
          >
            {getPageName(seg, i)}
          </button>
        </span>
      ))}
    </div>
  );
}
