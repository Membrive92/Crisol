'use client';

import Link from 'next/link';

import { colors, fontSize, fontWeight, layout, spacing } from '@crisol/ui';

import { CycleSettings } from '@/components/settings/cycle-settings';

/**
 * C2 — Sub-página de Ajustes: «el mes lo defines tú».
 *
 * La página es una cáscara a propósito. Todo el comportamiento (el selector, la
 * previsualización con movimientos reales, el guardado) vive en
 * `components/settings/`, que es donde puede probarse sin arrastrar el router
 * de Next.
 */
export default function CycleSettingsPage() {
  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      <Link
        href="/settings"
        style={{
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textDecoration: 'none',
        }}
      >
        ← Ajustes
      </Link>

      <header style={{ marginTop: spacing.sm, marginBottom: spacing.lg }}>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          Tu mes
        </h1>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Decide en qué día empieza tu mes. Es un ajuste de presentación: cambia
          por dónde se cortan los períodos, no tus datos.
        </p>
      </header>

      <CycleSettings />
    </div>
  );
}
