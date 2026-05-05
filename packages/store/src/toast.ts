import { create } from 'zustand';

import type { Toast, ToastInput, ToastKind } from '@finanzas/types';

/**
 * Defaults de auto-dismiss por kind. `error` queda en 0 (manual)
 * porque tragar un error en silencio frustra al usuario; con acción
 * subimos a 8s para que dé tiempo a leerla y pulsarla.
 */
const DEFAULT_DISMISS_MS: Record<ToastKind, number> = {
  info: 5000,
  success: 5000,
  warning: 6000,
  error: 0,
};

const DEFAULT_DISMISS_MS_WITH_ACTION = 8000;

export interface ToastState {
  toasts: Toast[];
  /** Encola un toast y devuelve su id (útil para `dismiss(id)` programático). */
  show: (input: ToastInput) => string;
  /** Quita un toast por id. No-op si no existe. */
  dismiss: (id: string) => void;
  /** Vacía la queue. Usado en tests; raro en prod. */
  clear: () => void;
}

function generateId(): string {
  // crypto.randomUUID está en RN ≥0.74 y en todos los navegadores
  // modernos. Fallback a Date.now()+random por si algún runtime exótico.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Sistema de toasts global cross-platform (PHASE-11.3).
 *
 * Patrón: cualquier código llama `useToastStore.getState().show({...})`
 * (sin necesidad de hook); el `<Toaster />` montado en el root layout
 * lee la queue con `useToastStore((s) => s.toasts)` y la renderiza
 * con auto-dismiss.
 *
 * Sin persist — los toasts son ephemerals por sesión.
 */
export const useToastStore = create<ToastState>()((set) => ({
  toasts: [],

  show: (input) => {
    const id = generateId();
    const kind: ToastKind = input.kind ?? 'info';
    const dismissAfterMs =
      input.dismissAfterMs ??
      (input.action ? DEFAULT_DISMISS_MS_WITH_ACTION : DEFAULT_DISMISS_MS[kind]);
    const toast: Toast = {
      id,
      kind,
      message: input.message,
      ...(input.action ? { action: input.action } : {}),
      dismissAfterMs,
    };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    return id;
  },

  dismiss: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },

  clear: () => set({ toasts: [] }),
}));

/**
 * API procedural para callers que no quieren llamar a `useToastStore.getState()`.
 *
 *   import { toast } from '@finanzas/store';
 *   toast.success('Guardado');
 *   toast.show({ kind: 'info', message: '...', action: { label: 'Deshacer', onPress } });
 */
export const toast = {
  show: (input: ToastInput) => useToastStore.getState().show(input),
  info: (message: string) =>
    useToastStore.getState().show({ kind: 'info', message }),
  success: (message: string) =>
    useToastStore.getState().show({ kind: 'success', message }),
  warning: (message: string) =>
    useToastStore.getState().show({ kind: 'warning', message }),
  error: (message: string) =>
    useToastStore.getState().show({ kind: 'error', message }),
  dismiss: (id: string) => useToastStore.getState().dismiss(id),
  clear: () => useToastStore.getState().clear(),
};
