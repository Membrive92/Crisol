'use client';

import { colors, fontSize, spacing } from '@finanzas/ui';

/**
 * Separador horizontal con texto "o" en medio. Se usa entre el botón
 * principal de login con password y el botón alternativo de passkey.
 */
export function PasskeyDivider() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        margin: `${spacing.xs}px 0`,
      }}
      aria-hidden="true"
    >
      <span style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
      <span
        style={{
          fontSize: fontSize.xs,
          color: colors.textSubtle,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
        }}
      >
        o
      </span>
      <span style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
    </div>
  );
}
