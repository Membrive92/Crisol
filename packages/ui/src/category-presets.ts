/**
 * Presets visuales para categorías de finanzas personales.
 *
 * Compartidos entre web y mobile para que la pantalla de gestión
 * presente la misma paleta y los mismos emojis en ambos clientes.
 *
 * Los hex de `CATEGORY_COLOR_PALETTE` están alineados con los colores
 * que el seed asigna a las categorías recomendadas (ver
 * `backend/.../seed/dataset.py`). Mantener ambas listas en sincronía.
 */

export interface CategoryColorPreset {
  /** Identificador estable para tests/serialización. */
  id: string;
  /** Hex `#RRGGBB`. Se persiste tal cual en `categories.color`. */
  hex: string;
  /** Nombre humano corto, sirve como label/tooltip. */
  label: string;
}

export const CATEGORY_COLOR_PALETTE: readonly CategoryColorPreset[] = [
  { id: 'red', hex: '#ef4444', label: 'Rojo' },
  { id: 'orange', hex: '#f97316', label: 'Naranja' },
  { id: 'amber', hex: '#f59e0b', label: 'Ámbar' },
  { id: 'yellow', hex: '#eab308', label: 'Amarillo' },
  { id: 'lime', hex: '#22c55e', label: 'Lima' },
  { id: 'emerald', hex: '#10b981', label: 'Esmeralda' },
  { id: 'green', hex: '#16a34a', label: 'Verde' },
  { id: 'teal', hex: '#14b8a6', label: 'Verde azulado' },
  { id: 'cyan', hex: '#06b6d4', label: 'Cian' },
  { id: 'sky', hex: '#0ea5e9', label: 'Cielo' },
  { id: 'indigo', hex: '#6366f1', label: 'Índigo' },
  { id: 'violet', hex: '#8b5cf6', label: 'Violeta' },
  { id: 'purple', hex: '#a855f7', label: 'Morado' },
  { id: 'pink', hex: '#ec4899', label: 'Rosa' },
  { id: 'rose', hex: '#f43f5e', label: 'Carmesí' },
  { id: 'slate', hex: '#64748b', label: 'Pizarra' },
  { id: 'graphite', hex: '#475569', label: 'Grafito' },
  { id: 'silver', hex: '#94a3b8', label: 'Plata' },
] as const;

/**
 * Lista curada de emojis sugeridos para categorías. El usuario puede
 * elegir uno con un tap; el campo `icon` admite cualquier string así
 * que esto es sólo el set por defecto del picker.
 */
export const CATEGORY_EMOJI_PRESETS: readonly string[] = [
  '🍽️',
  '🛒',
  '⛽',
  '🚌',
  '🚗',
  '✈️',
  '📺',
  '🎬',
  '🎮',
  '🎵',
  '💊',
  '🏥',
  '🏠',
  '💡',
  '📱',
  '📦',
  '🛍️',
  '🏬',
  '👕',
  '🎁',
  '💸',
  '💰',
  '💳',
  '🏦',
  '↔️',
  '📈',
  '🛡️',
  '🐶',
  '📚',
  '🎓',
  '🧾',
  '🍼',
  '🧘',
  '☕',
] as const;

/** Hex del primer color de la paleta — fallback si no hay color elegido. */
export const DEFAULT_CATEGORY_COLOR = CATEGORY_COLOR_PALETTE[0]!.hex;
