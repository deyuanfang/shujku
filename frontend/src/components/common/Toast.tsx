import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

interface Props {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

const ICONS = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const COLORS = {
  success: 'border-emerald-600/30 bg-emerald-600/10 text-emerald-400',
  error: 'border-red-600/30 bg-red-600/10 text-red-400',
  warning: 'border-amber-600/30 bg-amber-600/10 text-amber-400',
  info: 'border-blue-600/30 bg-blue-600/10 text-blue-400',
};

export default function ToastContainer({ toasts, onDismiss }: Props) {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: (id: string) => void }) {
  const [visible, setVisible] = useState(false);
  const Icon = ICONS[toast.type];

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    if (toast.duration !== 0) {
      const timer = setTimeout(() => setVisible(false), toast.duration || 4000);
      const dismiss = setTimeout(() => onDismiss(toast.id), (toast.duration || 4000) + 300);
      return () => { clearTimeout(timer); clearTimeout(dismiss); };
    }
  }, []);

  return (
    <div
      className={`
        glass-panel p-4 border flex items-start gap-3 transition-all duration-300
        ${COLORS[toast.type]}
        ${visible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'}
      `}
    >
      <Icon size={18} className="flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{toast.title}</p>
        {toast.message && <p className="text-xs opacity-70 mt-0.5">{toast.message}</p>}
      </div>
      <button onClick={() => onDismiss(toast.id)} className="opacity-50 hover:opacity-100">
        <X size={14} />
      </button>
    </div>
  );
}

// Toast store
let toastListeners: Array<(toasts: ToastMessage[]) => void> = [];
let currentToasts: ToastMessage[] = [];

export function showToast(type: ToastMessage['type'], title: string, message?: string) {
  const id = Math.random().toString(36).slice(2);
  currentToasts = [...currentToasts, { id, type, title, message }];
  toastListeners.forEach((fn) => fn(currentToasts));
  return id;
}

export function dismissToast(id: string) {
  currentToasts = currentToasts.filter((t) => t.id !== id);
  toastListeners.forEach((fn) => fn(currentToasts));
}

export function useToastStore() {
  const [toasts, setToasts] = useState<ToastMessage[]>(currentToasts);

  useEffect(() => {
    toastListeners.push(setToasts);
    return () => { toastListeners = toastListeners.filter((fn) => fn !== setToasts); };
  }, []);

  return { toasts, dismiss: dismissToast };
}
