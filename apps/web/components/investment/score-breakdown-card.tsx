'use client';

import { useState } from 'react';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { MetricDefinition, MetricResult, ScoreBreakdown, ThresholdSpec } from '@crisol/types';

import { BandChip } from './band-chip';
import { HelpButton, helpTextStyle } from './help-toggle';
import { formatMetricValue, formatThreshold } from '@crisol/ui';
import {
  effectiveThreshold,
  scoreBreakdownRows,
  type CatalogIndex,
  type MetricIndex,
  type ScoreComponentRow,
  type ScoreHelpIndex,
} from '@crisol/ui';

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
  /** TODOS los desgloses del run: la delta necesita el ejercicio anterior. */
  breakdowns: readonly ScoreBreakdown[] | undefined;
  /** Ejercicio del veredicto. */
  year: number | undefined;
  /** Para la serie del score (PHASE-44.24.D). */
  index: MetricIndex;
  catalog: CatalogIndex;
  thresholdsUsed: Record<string, ThresholdSpec> | undefined;
  /** Variante del modelo (`Z''(1995)`), cuando el run la declara. */
  variant?: string | null | undefined;
  /**
   * Fichas del engine: la del score y el nombre de cada una de sus variables.
   * Sin ellas la tarjeta imprimía la clave cruda (`DSRI`, `P4_cfo_supera_beneficio`).
   */
  help?: ScoreHelpIndex | undefined;
}

export function ScoreBreakdownCard({
  metricKey,
  metric,
  breakdowns,
  year,
  index,
  catalog,
  thresholdsUsed,
  variant,
  help,
}: ScoreBreakdownCardProps) {
  const [helpOpen, setHelpOpen] = useState(false);
  const ficha = help?.score(metricKey);
  const base = catalog.definition(metricKey);
  const definition: MetricDefinition | undefined = effectiveThreshold(
    metricKey,
    thresholdsUsed,
    base,
  );
  const threshold = formatThreshold(definition);
  const notComputable = !metric || metric.status === 'not_computable';

  // El desglose lo arma `@crisol/ui`: la delta frente al ejercicio anterior y el
  // orden se deciden una vez y las dos apps pintan lo mismo (PHASE-44.24.D).
  const view = scoreBreakdownRows(metricKey, breakdowns, year, index, definition?.unit, help);
  const components = view.rows.filter((row) => row.kind === 'component');
  const checks = view.rows.filter((row) => row.kind === 'check');

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
          {ficha ? (
            <>
              {' '}
              <HelpButton
                label={base?.label ?? metricKey}
                help={ficha.what}
                open={helpOpen}
                onToggle={() => setHelpOpen((v) => !v)}
              />
            </>
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
          {view.spark ? <ScoreSpark spark={view.spark} /> : null}
          <BandChip band={metric?.band ?? null} title={threshold ?? undefined} />
        </div>
      </div>

      {threshold ? (
        <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>{threshold}</span>
      ) : null}

      {/* Los tres campos separados y no una parrafada: «qué mide» se lee siempre,
          «por qué importa» sólo la primera vez, y «cómo se lee» es lo que se
          vuelve a consultar. Juntos obligarían a releer los tres cada vez. */}
      {helpOpen && ficha ? (
        <div style={{ ...helpTextStyle, borderRadius: radius.sm, borderBottom: 'none' }}>
          <p style={{ margin: 0 }}>{ficha.what}</p>
          <p style={{ margin: `${spacing.xs}px 0 0` }}>
            <strong style={{ color: colors.text }}>Por qué importa: </strong>
            {ficha.why}
          </p>
          <p style={{ margin: `${spacing.xs}px 0 0` }}>
            <strong style={{ color: colors.text }}>Cómo se lee: </strong>
            {ficha.reading}
          </p>
        </div>
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
          {components.map((row) => (
            <div key={row.key} style={{ display: 'contents' }}>
              <dt style={{ color: colors.textMuted, fontSize: fontSize.xs }} title={row.help}>
                {row.label}
              </dt>
              <dd
                style={{
                  margin: 0,
                  textAlign: 'right',
                  color: colors.text,
                  fontSize: fontSize.xs,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {row.value}
                <DeltaTag row={row} />
              </dd>
            </div>
          ))}
        </dl>
      ) : null}

      {checks.length > 0 ? (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 2 }}>
          {checks.map((row) => (
            <li
              key={row.key}
              style={{
                display: 'flex',
                gap: spacing.xs,
                color: row.passed ? colors.success : colors.textMuted,
                fontSize: fontSize.xs,
              }}
            >
              <span aria-hidden>{row.passed ? '✓' : '✕'}</span>
              <span title={row.help}>{row.label}</span>
              <DeltaTag row={row} />
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

/**
 * La variación de una variable frente al ejercicio anterior.
 *
 * Sin ella la tarjeta enseña un NIVEL, y un DSRI de 1,08 no significa nada
 * suelto: lo que Beneish detecta es el movimiento. `null` (no hay ejercicio
 * anterior con desglose) no pinta nada — un «=» ahí afirmaría una comparación
 * que no se ha hecho.
 */
function DeltaTag({ row }: { row: ScoreComponentRow }) {
  if (row.delta === null) return null;
  const color =
    row.direction === 'up'
      ? colors.text
      : row.direction === 'down'
        ? colors.text
        : colors.textSubtle;
  return (
    <span
      style={{ marginLeft: spacing.xs, color, fontSize: fontSize.xs }}
      title={`Frente al ejercicio anterior: ${row.delta}`}
    >
      {row.delta}
    </span>
  );
}

/** La serie del score, en 40×12. Misma forma que la de la matriz. */
function ScoreSpark({
  spark,
}: {
  spark: NonNullable<ReturnType<typeof scoreBreakdownRows>['spark']>;
}) {
  const width = 40;
  const height = 12;
  const points = spark.points
    .map(
      (point) => `${(point.x * width).toFixed(1)},${((1 - point.y) * (height - 2) + 1).toFixed(1)}`,
    )
    .join(' ');
  const stroke =
    spark.trend === 'up'
      ? colors.success
      : spark.trend === 'down'
        ? colors.danger
        : colors.textMuted;
  return (
    <svg width={width} height={height} role="img" aria-label={spark.ariaLabel}>
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={1.5} />
    </svg>
  );
}
