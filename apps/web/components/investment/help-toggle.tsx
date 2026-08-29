'use client';

import type { CSSProperties } from 'react';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

/**
 * La «i» que explica qué es un concepto del informe (PHASE-44.23).
 *
 * Vive aparte porque la usan dos renderizadores distintos: la matriz
 * concepto × ejercicio (Estados, Ratios, Evolución, Forense, Dividendo) y la
 * tabla de Valoración, que no es una matriz porque sus múltiplos no tienen
 * serie —se calculan contra la cotización de HOY—. Duplicar el afordance sería
 * la forma habitual de que una pestaña acabe explicando sus filas y la de al
 * lado no.
 *
 * Es un `button` y no un `title=` a secas: un tooltip nativo no lo abre el
 * teclado, y el texto son dos o tres frases que en un tooltip taparían la
 * tabla. El `title` se pone IGUALMENTE, porque para quien va con ratón leerlo
 * al pasar por encima es más rápido que pulsar.
 */
export function HelpButton({
  label,
  help,
  open,
  onToggle,
}: {
  label: string;
  help: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-label={`Qué es «${label}»`}
      title={help}
      style={{
        border: 'none',
        background: 'transparent',
        padding: 0,
        cursor: 'help',
        color: open ? colors.primary : colors.textSubtle,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        lineHeight: 1,
      }}
    >
      ⓘ
    </button>
  );
}

/** El panel con la definición, desplegado bajo la fila. */
export const helpTextStyle: CSSProperties = {
  padding: `${spacing.xs}px ${spacing.sm}px ${spacing.sm}px`,
  color: colors.textMuted,
  fontSize: fontSize.xs,
  lineHeight: 1.55,
  backgroundColor: colors.surfaceMuted,
  borderBottom: `1px solid ${colors.border}`,
};
