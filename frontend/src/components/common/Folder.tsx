import { useState } from 'react';
import './Folder.css';

const darkenColor = (hex: string, percent: number): string => {
  let color = hex.startsWith('#') ? hex.slice(1) : hex;
  if (color.length === 3) color = color.split('').map(c => c + c).join('');
  const num = parseInt(color, 16);
  let r = Math.max(0, Math.min(255, Math.floor(((num >> 16) & 0xff) * (1 - percent))));
  let g = Math.max(0, Math.min(255, Math.floor(((num >> 8) & 0xff) * (1 - percent))));
  let b = Math.max(0, Math.min(255, Math.floor((num & 0xff) * (1 - percent))));
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase();
};

interface Props {
  color?: string;
  size?: number;
  items?: React.ReactNode[];
  label?: string;
  count?: number;
  onClick?: () => void;
  className?: string;
}

export default function Folder({ color = '#6366f1', size = 1, items = [], label, count, onClick, className = '' }: Props) {
  const maxItems = 3;
  const papers = items.slice(0, maxItems);
  while (papers.length < maxItems) papers.push(null);

  const [open, setOpen] = useState(false);
  const [paperOffsets, setPaperOffsets] = useState(
    Array.from({ length: maxItems }, () => ({ x: 0, y: 0 }))
  );

  const folderBackColor = darkenColor(color, 0.08);
  const paperColors = [
    darkenColor('#1e293b', 0.0),
    darkenColor('#1e293b', -0.08),
    darkenColor('#1e293b', -0.15),
  ];

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOpen(prev => !prev);
    if (open) setPaperOffsets(Array.from({ length: maxItems }, () => ({ x: 0, y: 0 })));
    onClick?.();
  };

  const handlePaperMouseMove = (e: React.MouseEvent, index: number) => {
    if (!open) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    setPaperOffsets(prev => {
      const next = [...prev];
      next[index] = { x: (e.clientX - centerX) * 0.15, y: (e.clientY - centerY) * 0.15 };
      return next;
    });
  };

  const handlePaperMouseLeave = (_e: React.MouseEvent, index: number) => {
    setPaperOffsets(prev => { const next = [...prev]; next[index] = { x: 0, y: 0 }; return next; });
  };

  const folderStyle = {
    '--folder-color': color,
    '--folder-back-color': folderBackColor,
    '--paper-1': paperColors[0],
    '--paper-2': paperColors[1],
    '--paper-3': paperColors[2],
  } as React.CSSProperties;

  return (
    <div style={{ transform: `scale(${size})`, transformOrigin: 'top center' }} className={className}>
      <div className={`folder ${open ? 'open' : ''}`.trim()} style={folderStyle}
        onClick={handleClick}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(e as any); } }}
        tabIndex={0} role="button" aria-expanded={open}>

        <div className="folder__back">
          {papers.map((item, i) => (
            <div key={i} className={`paper paper-${i + 1}`}
              onMouseMove={e => handlePaperMouseMove(e, i)}
              onMouseLeave={e => handlePaperMouseLeave(e, i)}
              style={open ? { '--magnet-x': `${paperOffsets[i]?.x || 0}px`, '--magnet-y': `${paperOffsets[i]?.y || 0}px` } as React.CSSProperties : {}}>
              {item}
            </div>
          ))}
          <div className="folder__front" />
          <div className="folder__front right" />
        </div>
      </div>

      {/* Label */}
      {label && (
        <div className="text-center mt-1.5">
          <p className="text-[11px] font-medium text-gray-300 truncate max-w-[100px]">{label}</p>
          {count !== undefined && <p className="text-[9px] text-gray-600">{count} 项</p>}
        </div>
      )}
    </div>
  );
}
