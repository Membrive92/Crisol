'use client';

import {
  canStepNext,
  canStepPrev,
  clampAnchor,
  periodLabel,
  stepAnchor,
} from '@crisol/services';
import type { DebtTimeRange } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { StitchPeriodToggle } from '@/components/analysis/stitch-period-toggle';
import { DatePicker } from '@/components/ui/date-picker';

export interface PeriodNavigatorProps {
  range: DebtTimeRange;
  onRangeChange: (range: DebtTimeRange) => void;
  /** Mes ancla `YYYY-MM` del período mostrado. */
  anchor: string;
  onAnchorChange: (anchor: string) => void;
  availableFrom: string | null;
  availableTo: string | null;
  /**
   * PHASE-41 — expone la opción "Personalizado" (rango libre `from/to`).
   * Off por defecto: sólo donde el consumidor sabe manejar `range='custom'`.
   */
  allowCustom?: boolean;
  /** Rango libre activo (day-strings `YYYY-MM-DD`), sólo con `range='custom'`. */
  customFrom?: string | null;
  customTo?: string | null;
  onCustomRangeChange?: (from: string, to: string) => void;
}

/**
 * PHASE-30.8 / PHASE-41 — Navegador de período: granularidad (Mes / Año /
 * Personalizado, vía `StitchPeriodToggle`) + flechas ◀ ▶ para los períodos
 * navegables, o dos date-pickers para el rango libre `custom`. Limitado al
 * rango con datos (`availableFrom`/`availableTo`).
 */
export function PeriodNavigator({
  range,
  onRangeChange,
  anchor,
  onAnchorChange,
  availableFrom,
  availableTo,
  allowCustom = false,
  customFrom = null,
  customTo = null,
  onCustomRangeChange,
}: PeriodNavigatorProps) {
  // PHASE-41 — `custom` (rango libre) no navega: las flechas/label sólo
  // aplican a los períodos navegables (month/year). Los guards estrechan
  // el tipo a `NavigableRange` para los helpers puros.
  const prevEnabled = range !== 'custom' && canStepPrev(range, anchor, availableFrom);
  const nextEnabled = range !== 'custom' && canStepNext(range, anchor, availableTo);

  function handleRangeChange(next: DebtTimeRange) {
    onRangeChange(next);
    // Re-snap + re-clamp el ancla a la nueva granularidad (custom no navega).
    if (next !== 'custom') {
      onAnchorChange(clampAnchor(next, anchor, availableFrom, availableTo));
    }
  }

  function step(direction: 1 | -1) {
    if (range === 'custom') return;
    onAnchorChange(
      clampAnchor(
        range,
        stepAnchor(range, anchor, direction),
        availableFrom,
        availableTo,
      ),
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        flexWrap: 'wrap',
      }}
    >
      <StitchPeriodToggle
        value={range}
        onChange={handleRangeChange}
        options={allowCustom ? ['month', 'year', 'custom'] : ['month', 'year']}
      />
      {range === 'custom' ? (
        <div
          style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.xs }}
          role="group"
          aria-label="Rango de fechas"
        >
          <DatePicker
            value={customFrom}
            max={customTo}
            onChange={(from) => onCustomRangeChange?.(from, customTo ?? '')}
            ariaLabel="Desde"
          />
          <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>–</span>
          <DatePicker
            value={customTo}
            min={customFrom}
            onChange={(to) => onCustomRangeChange?.(customFrom ?? '', to)}
            ariaLabel="Hasta"
          />
        </div>
      ) : (
        <div
          style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.xs }}
          role="group"
          aria-label="Navegar período"
        >
          <ArrowButton direction="prev" disabled={!prevEnabled} onClick={() => step(-1)} />
          <span
            style={{
              minWidth: 124,
              textAlign: 'center',
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {periodLabel(range, anchor)}
          </span>
          <ArrowButton direction="next" disabled={!nextEnabled} onClick={() => step(1)} />
        </div>
      )}
    </div>
  );
}

function ArrowButton({
  direction,
  disabled,
  onClick,
}: {
  direction: 'prev' | 'next';
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === 'prev' ? 'Período anterior' : 'Período siguiente'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 32,
        height: 32,
        borderRadius: radius.sm,
        border: `1px solid ${colors.border}`,
        backgroundColor: colors.surface,
        color: disabled ? colors.textSubtle : colors.text,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        fontSize: fontSize.lg,
        lineHeight: 1,
        padding: 0,
      }}
    >
      {direction === 'prev' ? '‹' : '›'}
    </button>
  );
}
