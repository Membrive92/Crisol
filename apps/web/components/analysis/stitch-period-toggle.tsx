'use client';

import { colors, fontSize, fontWeight, radius } from '@crisol/ui';

// PHASE-41 — `custom` = rango libre `from/to` (sin navegación); se eliminó
// `quarter` (sin sentido para un particular).
export type PeriodKey = 'month' | 'year' | 'custom';

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

/**
 * PHASE-34 — Rango de fechas ISO `[inicio, fin]` del período
 * (mes / trimestre / año) que CONTIENE el mes `anchor` (`YYYY-MM`).
 *
 * Normaliza internamente al primer mes del período, así que da igual si el
 * ancla es el mes en curso (p. ej. `2026-06` con `year` → todo 2026) o ya el
 * inicio.
 *
 * AUDIT-2026-07 (LOW): los límites se construyen en UTC (`Date.UTC`), igual
 * que el TimeSelector de /transactions. Antes usaba `new Date(año, mes, día)`
 * en hora LOCAL del navegador y emitía `toISOString()`, lo que en Europe/Madrid
 * desplazaba la frontera 1-2 h (una tx del día 1 a las 00:00 podía caer en el
 * mes anterior). Con UTC-midnight el rango coincide con el criterio del backend.
 */
export function boundsForAnchor(
  period: Exclude<PeriodKey, 'custom'>,
  anchor: string,
): { dateFrom: string; dateTo: string } {
  const parts = anchor.split('-');
  const year = Number(parts[0]);
  const month = Number(parts[1]); // 1-12
  const startMonthIdx = period === 'month' ? month - 1 : 0; // year
  const monthsInPeriod = period === 'month' ? 1 : 12;
  const start = new Date(Date.UTC(year, startMonthIdx, 1));
  const end = new Date(Date.UTC(year, startMonthIdx + monthsInPeriod, 0, 23, 59, 59));
  return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
}

// PHASE-41 — `boundsForCustomRange` (rango libre `custom`) vive ahora en
// `@crisol/services` (compartido web+móvil). Se reexporta aquí para no romper
// los imports existentes de este módulo.
export { boundsForCustomRange } from '@crisol/services';
