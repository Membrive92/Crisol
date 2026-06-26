'use client';

import type { DashboardSummary, MonthlyBucket } from '@crisol/types';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';
import { formatAmount } from '@crisol/ui';

import { Card } from '@/components/ui/card';
import { TrendingDownIcon, TrendingUpIcon } from '@/components/ui/icons';

export interface StitchKeyMetricsProps {
  summary: DashboardSummary | undefined;
  currency: string;
  /**
   * PHASE-29.6 — buckets mensuales del año en curso. Alimentan la
   * mini sparkline del card de "Flujo de caja neto". Si no se pasan,
   * la sparkline simplemente no se renderiza (degradación amable).
   */
  monthly?: MonthlyBucket[];
}

/**
 * Dos cards apiladas en la columna derecha del bento de Análisis:
 *  - Net Cash Flow: cifra + delta vs periodo previo + mini sparkline
 *    de los netos mensuales (PHASE-29.6).
 *  - Saving Rate: cifra + barra centrada en 0 que admite valores
 *    negativos (PHASE-29.6, antes era barra lineal 0-100% que no
 *    representaba nada cuando el ratio era negativo).
 */
export function StitchKeyMetrics({ summary, currency, monthly }: StitchKeyMetricsProps) {
  const balance = summary ? Number(summary.balance) : 0;
  const previousBalance =
    summary?.previous_period_balance != null ? Number(summary.previous_period_balance) : null;
  const incomeNum = summary ? Number(summary.income) : 0;
  const savingRate = incomeNum > 0 ? (balance / incomeNum) * 100 : null;
  const balanceDelta =
    previousBalance !== null && previousBalance !== 0
      ? ((balance - previousBalance) / Math.abs(previousBalance)) * 100
      : null;

  const monthlyNets =
    monthly && monthly.length > 0
      ? monthly.map((m) => Number(m.income) - Number(m.expenses))
      : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <Card style={{ padding: spacing.lg }}>
        <span
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.medium,
            color: colors.textMuted,
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          Flujo de caja neto
        </span>
        <span
          style={{
            display: 'block',
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: balance >= 0 ? colors.success : colors.danger,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {summary
            ? `${balance >= 0 ? '+' : ''}${formatAmount(summary.balance, currency)}`
            : '—'}
        </span>
        {balanceDelta !== null ? (
          <div
            style={{
              marginTop: spacing.md,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              color: balanceDelta >= 0 ? colors.success : colors.danger,
              fontSize: fontSize.xs,
              fontWeight: fontWeight.semibold,
            }}
          >
            {balanceDelta >= 0 ? <TrendingUpIcon size={14} /> : <TrendingDownIcon size={14} />}
            {balanceDelta >= 0 ? '+' : ''}
            {balanceDelta.toFixed(1)}% vs periodo anterior
          </div>
        ) : (
          <span
            style={{
              marginTop: spacing.md,
              display: 'inline-block',
              fontSize: fontSize.xs,
              color: colors.textSubtle,
            }}
          >
            Sin periodo previo para comparar
          </span>
        )}

        {monthlyNets ? (
          <div
            style={{
              marginTop: spacing.md,
              paddingTop: spacing.sm,
              borderTop: `1px solid ${colors.border}`,
            }}
          >
            <span
              style={{
                fontSize: 10,
                fontWeight: fontWeight.semibold,
                color: colors.textMuted,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                display: 'block',
                marginBottom: 6,
              }}
            >
              Neto mensual
            </span>
            <NetSparkline values={monthlyNets} negativeTotal={balance < 0} />
          </div>
        ) : null}
      </Card>

      <Card style={{ padding: spacing.lg }}>
        <span
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.medium,
            color: colors.textMuted,
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          Tasa de ahorro
        </span>
        <span
          style={{
            display: 'block',
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color:
              savingRate !== null && savingRate >= 0
                ? colors.primary
                : colors.danger,
            letterSpacing: '-0.01em',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.15,
          }}
        >
          {savingRate !== null ? `${savingRate.toFixed(1)}%` : '—'}
        </span>
        {savingRate !== null && savingRate < 0 ? (
          <span
            style={{
              display: 'block',
              marginTop: 2,
              fontSize: fontSize.xs,
              color: colors.textSubtle,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {/* Ratio adimensional: NO lleva símbolo de divisa (sería
                el mismo en numerador y denominador). Coma decimal es-ES. */}
            Gastas{' '}
            {(Math.abs(balance) / Math.max(incomeNum, 1) + 1).toLocaleString(
              'es-ES',
              { minimumFractionDigits: 2, maximumFractionDigits: 2 },
            )}{' '}
            por cada 1 ingresado
          </span>
        ) : null}
        <CenteredRateBar rate={savingRate} />
      </Card>
    </div>
  );
}

/**
 * Sparkline minimalista para la card de cash-flow. Path con gradient
 * fill y un círculo en el último punto. Sin libs externas — el dataset
 * típico son 12 puntos y dibujar un <path> a mano queda compacto.
 */
function NetSparkline({ values, negativeTotal }: { values: number[]; negativeTotal: boolean }) {
  const width = 260;
  const height = 42;
  const padY = 4;
  if (values.length < 2) {
    return (
      <p style={{ margin: 0, fontSize: 11, color: colors.textSubtle }}>
        Necesitas al menos 2 meses con datos para la sparkline.
      </p>
    );
  }
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const toY = (v: number) => padY + (1 - (v - min) / range) * (height - padY * 2);
  const points = values.map((v, i) => ({ x: i * stepX, y: toY(v) }));
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');
  const baselineY = toY(0);
  const last = points[points.length - 1] ?? { x: 0, y: padY };
  const stroke = negativeTotal ? colors.danger : colors.primary;
  const gradientId = `spark-${negativeTotal ? 'neg' : 'pos'}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      width="100%"
      height={height}
      aria-hidden
      style={{ display: 'block' }}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>
      {/* Baseline punteada en y(0) — referencia visual del cero. */}
      <line
        x1={0}
        x2={width}
        y1={baselineY}
        y2={baselineY}
        stroke={colors.borderStrong}
        strokeWidth={1}
        strokeDasharray="2 3"
        opacity={0.6}
      />
      {/* Fill bajo la línea. */}
      <path
        d={`${path} L ${width} ${height} L 0 ${height} Z`}
        fill={`url(#${gradientId})`}
      />
      <path d={path} stroke={stroke} strokeWidth={1.6} fill="none" />
      <circle
        cx={last.x}
        cy={last.y}
        r={3}
        fill={stroke}
        stroke={colors.surface}
        strokeWidth={1.5}
      />
    </svg>
  );
}

/**
 * Barra centrada en 0 para la tasa de ahorro. Acepta valores
 * negativos (gastas más de lo que ingresas) sin quedar como una
 * barra vacía. El marcador se posiciona en `50% + rate/2 %`, y la
 * "barra rellena" va desde el centro hasta el marcador, con color
 * según signo.
 */
function CenteredRateBar({ rate }: { rate: number | null }) {
  // Bound a [-100, 100] para no salirnos del ancho. Si el rate llega a
  // ser -150% (gastas el doble que ingresas), capamos visualmente.
  const bounded = rate === null ? 0 : Math.max(-100, Math.min(100, rate));
  const isNegative = bounded < 0;
  const markerLeft = 50 + bounded / 2; // 50 ± [0..50]
  const fillLeft = isNegative ? markerLeft : 50;
  const fillRight = isNegative ? 50 : markerLeft;
  const fillColor = isNegative ? colors.danger : colors.primary;
  const hasRate = rate !== null;
  return (
    <div style={{ marginTop: spacing.md }}>
      <div
        role="img"
        aria-label={
          hasRate
            ? `Tasa de ahorro ${rate.toFixed(1)}%`
            : 'Tasa de ahorro no disponible'
        }
        style={{
          position: 'relative',
          height: 6,
          borderRadius: 3,
          backgroundColor: colors.surfaceMuted,
          overflow: 'hidden',
        }}
      >
        {hasRate ? (
          <span
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${fillLeft}%`,
              right: `${100 - fillRight}%`,
              backgroundColor: fillColor,
              transition: 'left 200ms ease, right 200ms ease',
            }}
          />
        ) : null}
        {/* Línea de centro = 0%. */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: '50%',
            top: -2,
            bottom: -2,
            width: 1,
            backgroundColor: colors.border,
          }}
        />
      </div>
      <div
        style={{
          marginTop: 4,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          fontSize: 10,
          color: colors.textSubtle,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span style={{ textAlign: 'left' }}>−100 %</span>
        <span style={{ textAlign: 'center' }}>0</span>
        <span style={{ textAlign: 'right' }}>+100 %</span>
      </div>
    </div>
  );
}
