'use client';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { MetricDefinition, MetricResult, ScoreBreakdown, ThresholdSpec } from '@crisol/types';

import { BandChip } from './band-chip';
import { formatMetricValue, formatThreshold } from '@crisol/ui';
import { effectiveThreshold, type CatalogIndex } from '@crisol/ui';

/**
 * Las cuatro claves forenses que NUNCA emiten desglose, por diseño.
 *
 * Distinguir «no tiene desglose» de «este año no se pudo calcular» importa: el
 * primero es una propiedad del modelo, el segundo un hueco de datos. Sin la
 * distinción, `accruals` parecería siempre roto.
 */
const NO_BREAKDOWN_BY_DESIGN = new Set(['accruals', 'F5', 'F6', 'FZ']);

export interface ScoreBreakdownCardProps {
  metricKey: string;
  metric: MetricResult | undefined;
  breakdown: ScoreBreakdown | undefined;
  catalog: CatalogIndex;
  thresholdsUsed: Record<string, ThresholdSpec> | undefined;
  /** Variante del modelo (`Z''(1995)`), cuando el run la declara. */
  variant?: string | null | undefined;
}

export function ScoreBreakdownCard({
  metricKey,
  metric,
  breakdown,
  catalog,
  thresholdsUsed,
  variant,
}: ScoreBreakdownCardProps) {
  const base = catalog.definition(metricKey);
  const definition: MetricDefinition | undefined = effectiveThreshold(
    metricKey,
    thresholdsUsed,
    base,
  );
  const threshold = formatThreshold(definition);
  const notComputable = !metric || metric.status === 'not_computable';

  const components = Object.entries(breakdown?.components ?? {});
  const checks = Object.entries(breakdown?.checks ?? {});

  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: spacing.sm,
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{ color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold }}
        >
          {base?.label ?? metricKey}
          {variant ? (
            <span style={{ color: colors.textSubtle, fontWeight: fontWeight.regular }}>
              {' '}
              {variant}
            </span>
          ) : null}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
          <span
            style={{
              color: colors.text,
              fontSize: fontSize.md,
              fontWeight: fontWeight.bold,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {notComputable ? '—' : formatMetricValue(metric.value, definition?.unit)}
          </span>
          <BandChip band={metric?.band ?? null} title={threshold ?? undefined} />
        </div>
      </div>

      {threshold ? (
        <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>{threshold}</span>
      ) : null}

      {notComputable ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 1.5 }}>
          {metric?.reason ?? 'no se calculó en este ejercicio'}
        </p>
      ) : null}

      {base?.note ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 1.5 }}>
          {base.note}
        </p>
      ) : null}

      {components.length > 0 ? (
        <dl style={componentGridStyle}>
          {components.map(([name, value]) => (
            <div key={name} style={{ display: 'contents' }}>
              <dt style={{ color: colors.textMuted, fontSize: fontSize.xs }}>{name}</dt>
              <dd
                style={{
                  margin: 0,
                  textAlign: 'right',
                  color: colors.text,
                  fontSize: fontSize.xs,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {Number(value).toLocaleString('es-ES', { maximumFractionDigits: 3 })}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}

      {checks.length > 0 ? (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 2 }}>
          {checks.map(([name, passed]) => (
            <li
              key={name}
              style={{
                display: 'flex',
                gap: spacing.xs,
                color: passed ? colors.success : colors.textMuted,
                fontSize: fontSize.xs,
              }}
            >
              <span aria-hidden>{passed ? '✓' : '✕'}</span>
              <span>{name}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {components.length === 0 && checks.length === 0 && !notComputable ? (
        <p style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs }}>
          {NO_BREAKDOWN_BY_DESIGN.has(metricKey)
            ? 'Este score no tiene desglose por diseño: es un ratio único, no un agregado de componentes.'
            : 'Sin desglose para este ejercicio.'}
        </p>
      ) : null}
    </div>
  );
}

const componentGridStyle = {
  margin: 0,
  display: 'grid',
  gridTemplateColumns: '1fr auto',
  columnGap: spacing.md,
  rowGap: 2,
} as const;
