import { User, Building2, MapPin, Lightbulb, Calendar, Cpu, Hash } from 'lucide-react';

interface Entity {
  name: string;
  type: string;
  description?: string;
}

interface Props {
  entities: Entity[];
  onEntityClick?: (entity: Entity) => void;
}

const ICON_MAP: Record<string, typeof User> = {
  person: User,
  organization: Building2,
  location: MapPin,
  concept: Lightbulb,
  event: Calendar,
  technology: Cpu,
};

const COLOR_MAP: Record<string, string> = {
  person: 'text-amber-400 bg-amber-600/10 border-amber-600/20',
  organization: 'text-blue-400 bg-blue-600/10 border-blue-600/20',
  location: 'text-emerald-400 bg-emerald-600/10 border-emerald-600/20',
  concept: 'text-violet-400 bg-violet-600/10 border-violet-600/20',
  event: 'text-red-400 bg-red-600/10 border-red-600/20',
  technology: 'text-cyan-400 bg-cyan-600/10 border-cyan-600/20',
  other: 'text-gray-400 bg-gray-600/10 border-gray-600/20',
};

const TYPE_LABELS: Record<string, string> = {
  person: '人物',
  organization: '组织',
  location: '地点',
  concept: '概念',
  event: '事件',
  technology: '技术',
  other: '其他',
};

export default function EntityPanel({ entities, onEntityClick }: Props) {
  if (entities.length === 0) {
    return <p className="text-xs text-gray-600">未提取到实体</p>;
  }

  return (
    <div className="space-y-2">
      {entities.map((entity, i) => {
        const Icon = ICON_MAP[entity.type] || Hash;
        const colorClass = COLOR_MAP[entity.type] || COLOR_MAP.other;

        return (
          <button
            key={`${entity.name}-${i}`}
            onClick={() => onEntityClick?.(entity)}
            className={`
              w-full text-left flex items-start gap-3 p-2.5 rounded-lg border
              transition-all hover:scale-[1.02] cursor-pointer
              ${colorClass}
            `}
          >
            <Icon size={16} className="mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium truncate">{entity.name}</span>
                <span className="text-[10px] opacity-60 flex-shrink-0">
                  {TYPE_LABELS[entity.type] || entity.type}
                </span>
              </div>
              {entity.description && (
                <p className="text-xs opacity-70 mt-0.5 line-clamp-2">{entity.description}</p>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
