import { Tag } from 'lucide-react';

interface Props {
  tags: Array<{ name: string; count?: number; color?: string }>;
  onTagClick?: (tag: string) => void;
  size?: 'sm' | 'md' | 'lg';
}

const SIZE_MAP = {
  sm: 'text-[10px] px-2 py-0.5',
  md: 'text-xs px-2.5 py-1',
  lg: 'text-sm px-3 py-1.5',
};

const COLORS = [
  'bg-primary-600/20 text-primary-400 border-primary-600/30',
  'bg-emerald-600/20 text-emerald-400 border-emerald-600/30',
  'bg-amber-600/20 text-amber-400 border-amber-600/30',
  'bg-pink-600/20 text-pink-400 border-pink-600/30',
  'bg-cyan-600/20 text-cyan-400 border-cyan-600/30',
  'bg-violet-600/20 text-violet-400 border-violet-600/30',
];

export default function TagCloud({ tags, onTagClick, size = 'md' }: Props) {
  if (tags.length === 0) {
    return <p className="text-xs text-gray-600">暂无标签</p>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag, i) => (
        <button
          key={tag.name}
          onClick={() => onTagClick?.(tag.name)}
          className={`
            inline-flex items-center gap-1 rounded-full border
            transition-all hover:scale-105 cursor-pointer
            ${SIZE_MAP[size]}
            ${COLORS[i % COLORS.length]}
            ${tag.count ? 'font-medium' : ''}
          `}
          title={tag.count ? `使用 ${tag.count} 次` : undefined}
        >
          <Tag size={size === 'sm' ? 10 : 12} />
          {tag.name}
          {tag.count && tag.count > 1 && (
            <span className="opacity-60 ml-0.5">{tag.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
