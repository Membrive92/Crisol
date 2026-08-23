'use client';

import type { PeriodKey } from '@crisol/types';
import { colors, fontSize, fontWeight, radius } from '@crisol/ui';

// PHASE-41 — `custom` = rango libre `from/to` (sin navegación); se eliminó
// `quarter` (sin sentido para un particular).
// C0 — `PeriodKey` (con `cycle`) vive en `@crisol/types`: estaba declarado dos
// veces, una por app. Se reexporta aquí para no romper los imports existentes.
export type { PeriodKey };

export interface StitchPeriodToggleProps {
  value: PeriodKey;
  onChange: (next: PeriodKey) => void;
  /**
   * Opciones a mostrar. Por defecto `['month','year']`; pasa
   * `['month','year','custom']` donde el rango libre esté soportado.
   */
  options?: readonly PeriodKey[];
}

const LABELS: Record<PeriodKey, string> = {
  month: 'Mes',
  year: 'Año',
  custom: 'Personalizado',
};

/** Toggle Mes / Año / Personalizado al estilo Stitch (segmented). */
export function StitchPeriodToggle({
  value,
  onChange,
  options = ['month', 'year'],
}: StitchPeriodToggleProps) {
  return (
    <div
      style={{
        display: 'inline-flex',
        backgroundColor: colors.surfaceMuted,
        padding: 2,
        borderRadius: radius.md,
        border: `1px solid ${colors.border}`,
      }}
    >
      {options.map((opt) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            style={{
              padding: `6px 14px`,
              backgroundColor: active ? colors.surface : 'transparent',
              color: active ? colors.text : colors.textMuted,
              border: active ? `1px solid ${colors.borderStrong}` : '1px solid transparent',
              borderRadius: radius.sm,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              cursor: 'pointer',
            }}
          >
            {LABELS[opt]}
          </button>
        );
      })}
    </div>
  );
}

// PHASE-41 — `boundsForCustomRange` (rango libre `custom`) vive en
// `@crisol/services` (compartido web+móvil).
// C0 — `boundsForAnchor` (mes/año, UTC con ancla) se ha subido al mismo sitio:
// móvil tenía su propia copia en hora LOCAL y sin ancla, y con un corte
// día-exacto por ciclo las dos plataformas cortarían en instantes distintos.
// Ambas se reexportan aquí para no romper los imports existentes de este módulo.
export { boundsForAnchor, boundsForCustomRange } from '@crisol/services';
