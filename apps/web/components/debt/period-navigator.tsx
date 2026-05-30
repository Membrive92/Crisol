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

export interface PeriodNavigatorProps {
  range: DebtTimeRange;
  onRangeChange: (range: DebtTimeRange) => void;
  /** Mes ancla `YYYY-MM` del período mostrado. */
  anchor: string;
  onAnchorChange: (anchor: string) => void;
  availableFrom: string | null;
  availableTo: string | null;
}

/**
 * PHASE-30.8 — Navegador de período del módulo deuda: granularidad
 * (Mes / Trimestre / Año, vía `StitchPeriodToggle`) + flechas ◀ ▶ que
 * recorren períodos concretos, limitadas al rango con datos
 * (`availableFrom`/`availableTo`). Gobierna toda la página `/debt`.
 */
export function PeriodNavigator({
  range,
  onRangeChange,
  anchor,
  onAnchorChange,
  availableFrom,
  availableTo,
}: PeriodNavigatorProps) {
  const prevEnabled = canStepPrev(range, anchor, availableFrom);
  const nextEnabled = canStepNext(range, anchor, availableTo);

  function handleRangeChange(next: DebtTimeRange) {
    onRangeChange(next);
    // Re-snap + re-clamp el ancla a la nueva granularidad.
    onAnchorChange(clampAnchor(next, anchor, availableFrom, availableTo));
  }

  function step(direction: 1 | -1) {
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
      <StitchPeriodToggle value={range} onChange={handleRangeChange} />
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
