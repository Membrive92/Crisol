/**
 * Tipos del sistema de toasts global (PHASE-11.3).
 * El store vive en `@finanzas/store` (`useToastStore`); el render se
 * hace con un componente `<Toaster />` por plataforma.
 */

export type ToastKind = 'info' | 'success' | 'warning' | 'error';

/**
 * Acción opcional dentro de un toast (botón al lado del mensaje).
 * Sólo `label` + `onPress`. No incluimos `href` porque navegación
 * y mutaciones se mezclan mal en una sola UI primitive — si hace
 * falta navegar, el caller hace `router.push` desde su `onPress`.
 */
export interface ToastAction {
  label: string;
  onPress: () => void;
}

export interface Toast {
  /** Generado por el store (`crypto.randomUUID()`). Único por toast. */
  id: string;
  kind: ToastKind;
  message: string;
  /** Botón opcional al lado del mensaje. */
  action?: ToastAction;
  /**
   * Timeout antes de auto-dismiss. `0` = manual (sólo dismissable
   * por click en X o por código). Defaults los aplica el store.
   */
  dismissAfterMs: number;
}

/** Input público al `toast.show(...)` — el store rellena `id` y `dismissAfterMs` por defecto. */
export interface ToastInput {
  kind?: ToastKind;
  message: string;
  action?: ToastAction;
  dismissAfterMs?: number;
}
