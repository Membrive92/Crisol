'use client';

import { DEFAULT_CATEGORY_COLOR, fontSize } from '@finanzas/ui';

export interface AccountSwatchProps {
  color: string | null;
  icon: string | null;
  size?: number;
}

/**
 * Avatar circular para una cuenta — color de fondo + emoji opcional.
 * Coincide visualmente con `CategorySwatch` (settings/categories) por
 * coherencia: ambos representan entidades coloreables del usuario.
 */
export function AccountSwatch({ color, icon, size = 32 }: AccountSwatchProps) {
  const bg = color ?? DEFAULT_CATEGORY_COLOR;
  return (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: bg,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      {icon ? <span style={{ fontSize: fontSize.md, lineHeight: 1 }}>{icon}</span> : null}
    </span>
  );
}
