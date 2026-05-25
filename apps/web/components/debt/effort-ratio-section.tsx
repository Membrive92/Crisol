'use client';

import { useState } from 'react';

import type { EffortStatus } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';

export interface EffortRatioSectionProps {
  strictRatio: number | null;
  strictStatus: EffortStatus;
  extendedRatio: number | null;
  extendedStatus: EffortStatus;
  monthlyIncome: string;
  /** Monto absoluto (no ratio) que conforma el numerador estricto. */
  monthlyDebtPayment: string;
  /** Monto absoluto del numerador ampliado (deuda + gastos fijos). */
  monthlyDebtPaymentExtended: string;
  currency: string;
  isLoading: boolean;
}

type Mode = 'strict' | 'extended';

/**
 * PHASE-30.3 — Sección "Tasa de esfuerzo" de Capa 1.
 *
 * Muestra el ratio estricta (solo deuda / ingresos netos) con la
 * opción de cambiar a la ampliada (deuda + gastos fijos confirmados
 * no-deuda / ingresos netos). El gauge horizontal pinta las bandas
 * BdE 30%/35%; el thumb se posiciona en `ratio × 100` truncado a
 * [0, 50] para mantener la escala legible.
 *
 * Tooltip educativo en cada label porque la diferencia estricta vs.
 * ampliada es la que decide si el usuario actúa.
 */
export function EffortRatioSection({
  strictRatio,
  strictStatus,
  extendedRatio,
  extendedStatus,
  monthlyIncome,
  monthlyDebtPayment,
  monthlyDebtPaymentExtended,
  currency,
  isLoading,
}: EffortRatioSectionProps) {
  const [mode, setMode] = useState<Mode>('strict');

  const ratio = mode === 'strict' ? strictRatio : extendedRatio;
  const status = mode === 'strict' ? strictStatus : extendedStatus;
  const numerator =
    mode === 'strict' ? monthlyDebtPayment : monthlyDebtPaymentExtended;

  return (
    <Card
      style={{
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: fontSize.lg,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Tasa de esfuerzo
          </h2>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              maxWidth: 520,
              lineHeight: 1.5,
            }}
          >
            {mode === 'strict'
              ? '% de tus ingresos netos mensuales que va sólo a cuotas de deuda. El Banco de España recomienda no superar el 35%.'
              : 'Incluye también tus gastos fijos confirmados (suministros, seguros, suscripciones). Da una idea más realista de tu margen disponible.'}
          </p>
        </div>
        <ModeToggle mode={mode} onChange={setMode} />
      </header>

      <EffortGauge ratio={ratio} status={status} isLoading={isLoading} />

      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          lineHeight: 1.5,
        }}
      >
        <strong
          style={{
            color: colors.text,
            fontVariantNumeric: 'tabular-nums',
            fontWeight: fontWeight.semibold,
          }}
        >
          {formatAmount(numerator, currency)}
        </strong>{' '}
        de tus{' '}
        <strong
          style={{
            color: colors.text,
            fontVariantNumeric: 'tabular-nums',
            fontWeight: fontWeight.semibold,
          }}
        >
          {formatAmount(monthlyIncome, currency)}
        </strong>{' '}
        netos mensuales van a{' '}
        {mode === 'strict' ? 'deuda' : 'deuda + gastos fijos'}.
      </p>
    </Card>
  );
}

function ModeToggle({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Tipo de tasa de esfuerzo"
      style={{
        display: 'inline-flex',
        gap: 0,
        padding: 2,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
      }}
    >
      <ToggleButton
        active={mode === 'strict'}
        onClick={() => onChange('strict')}
        label="Estricta"
      />
      <ToggleButton
        active={mode === 'extended'}
        onClick={() => onChange('extended')}
        label="Ampliada"
      />
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      style={{
        padding: `${spacing.xs}px ${spacing.sm}px`,
        backgroundColor: active ? colors.surface : 'transparent',
        color: active ? colors.text : colors.textMuted,
        border: 'none',
        borderRadius: radius.sm,
        cursor: 'pointer',
        boxShadow: active ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
      }}
    >
      {label}
    </button>
  );
}

function EffortGauge({
  ratio,
  status,
  isLoading,
}: {
  ratio: number | null;
  status: EffortStatus;
  isLoading: boolean;
}) {
  const tone = effortTone(status);
  const pct = ratio !== null ? Math.max(0, Math.min(50, ratio * 100)) : null;
  const thumbLeft = pct !== null ? (pct / 50) * 100 : null;
  // Bandas a 0%, 30%, 35%, 50% (escala visual). Los thresholds visuales
  // son los mismos que las bandas del backend (30/35).
  const bandHealthyEnd = (30 / 50) * 100; // 60%
  const bandCautionEnd = (35 / 50) * 100; // 70%

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: spacing.sm,
        }}
      >
        <span
          style={{
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {isLoading
            ? '—'
            : pct !== null
              ? `${pct.toFixed(1)} %`
              : '—'}
        </span>
        <span
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.semibold,
            color: tone.fg,
            backgroundColor: tone.bg,
            padding: '2px 8px',
            borderRadius: radius.sm,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {tone.label}
        </span>
      </div>

      <div
        role="img"
        aria-label={
          ratio !== null
            ? `Tasa de esfuerzo del ${(ratio * 100).toFixed(1)} por ciento`
            : 'Sin datos de tasa de esfuerzo'
        }
        style={{
          position: 'relative',
          height: 12,
          borderRadius: 999,
          overflow: 'hidden',
          backgroundColor: colors.surfaceMuted,
          border: `1px solid ${colors.border}`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            width: '100%',
          }}
        >
          <div
            style={{
              width: `${bandHealthyEnd}%`,
              backgroundColor: colors.successSoft,
            }}
          />
          <div
            style={{
              width: `${bandCautionEnd - bandHealthyEnd}%`,
              backgroundColor: colors.warningSoft,
            }}
          />
          <div
            style={{
              width: `${100 - bandCautionEnd}%`,
              backgroundColor: colors.dangerSoft,
            }}
          />
        </div>
        {thumbLeft !== null ? (
          <div
            style={{
              position: 'absolute',
              top: -2,
              bottom: -2,
              left: `${thumbLeft}%`,
              width: 4,
              backgroundColor: colors.text,
              borderRadius: 2,
              transform: 'translateX(-50%)',
              boxShadow: `0 0 0 2px ${colors.surface}`,
            }}
          />
        ) : null}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 10,
          color: colors.textMuted,
          fontVariantNumeric: 'tabular-nums',
          marginTop: 2,
        }}
      >
        <span>0%</span>
        <span style={{ marginLeft: `${bandHealthyEnd - 2}%` }}>30%</span>
        <span style={{ marginLeft: 'auto', marginRight: `${100 - bandCautionEnd - 2}%` }}>35%</span>
        <span>50%</span>
      </div>
    </div>
  );
}

function effortTone(status: EffortStatus): { bg: string; fg: string; label: string } {
  switch (status) {
    case 'healthy':
      return { bg: colors.successSoft, fg: colors.success, label: 'Saludable' };
    case 'caution':
      return { bg: colors.warningSoft, fg: colors.warning, label: 'Precaución' };
    case 'stressed':
      return { bg: colors.dangerSoft, fg: colors.danger, label: 'Sobreendeudamiento' };
    case 'unknown':
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted, label: 'Sin datos' };
  }
}
