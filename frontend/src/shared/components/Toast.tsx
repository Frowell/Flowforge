/**
 * Toast notification system — Zustand store + container component.
 *
 * Usage: useToastStore.getState().addToast("Saved!", "success")
 */

import { useEffect } from "react";
import { create } from "zustand";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (message: string, type: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
}

let toastCounter = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (message, type, duration = 4000) => {
    const id = `toast-${++toastCounter}`;
    set((state) => ({
      toasts: [...state.toasts, { id, message, type, duration }],
    }));
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },
}));

const TYPE_STYLES: Record<ToastType, string> = {
  success: "bg-emerald-500/20 border-emerald-500/40 text-emerald-300",
  error: "bg-red-500/20 border-red-500/40 text-red-300",
  warning: "bg-yellow-500/20 border-yellow-500/40 text-yellow-300",
  info: "bg-blue-500/20 border-blue-500/40 text-blue-300",
};

function ToastItem({ toast }: { toast: Toast }) {
  const removeToast = useToastStore((s) => s.removeToast);

  useEffect(() => {
    const timer = setTimeout(() => removeToast(toast.id), toast.duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, removeToast]);

  return (
    <div
      className={`flex items-center gap-2 px-4 py-2.5 rounded border text-sm shadow-lg animate-in slide-in-from-right ${TYPE_STYLES[toast.type]}`}
    >
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={() => removeToast(toast.id)}
        className="text-white/40 hover:text-white text-xs shrink-0"
      >
        &times;
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
