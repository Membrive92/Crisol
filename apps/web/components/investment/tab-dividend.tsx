'use client';

import { colors, fontSize, fontWeight, REPORT_LEGEND, spacing } from '@crisol/ui';
import { DIVIDEND_BLOCKS as BLOCKS } from '@crisol/ui';
import type { AnalysisRun, Security } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { formatMetricValue } from '@crisol/ui';
import { metricRow, type MetricRowOptions } from '@crisol/ui';
import type { CatalogIndex, MetricIndex } from '@crisol/ui';
import { YearMatrix, type MatrixRow } from './year-matrix';

/** Los cuatro bloques de la capa 3, con las métricas que se calculan POR AÑO.
 *  T2 y T3 quedan fuera a propósito: el motor las emite una sola vez, para el
 *  último ejercicio, así que en una matriz saldrían con N−1 huecos
 *  indistinguibles de un «no calculable». Van en Trayectoria. */
export interface TabDividendProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  security: Security | undefined;
  /** Fila a la que se ha llegado desde el veredicto (PHASE-44.24.C.4). */
  highlightKey?: string | undefined;
}

export function TabDividend({ run, index, catalog, security, highlightKey }: TabDividendProps) {
  const dividend = run.dividend_analysis;
  const years = run.years_covered;
  const verdictYear = years[years.length - 1];
  const options: MetricRowOptions = { index, catalog, thresholdsUsed: run.thresholds_used };

  // `dividend_verdict === 'not_applicable'` colapsa DOS situaciones distintas
  // (`synthesis.py:520`): una financiera —aunque reparta— y una empresa que no
  // reparte. Ocultar la pestaña entera con esa etiqueta escondía ocho métricas
  // que el motor YA había calculado, con valor y banda, entre ellas las cuatro
  // de calidad de la caja, que no dependen del dividendo en absoluto
  // (PHASE-44.19).
  //
  // La pregunta «¿reparte?» se resuelve contra el RUN y no contra la fila viva
  // de `securities`: el run es la foto, y es lo que el usuario está mirando.
  const paysDividend = (dividend.dps_series ?? []).some(
    (point) => point.dps !== null && Number(point.dps) > 0,
  );
  const isFinancial = security?.is_financial === true;

  if (!paysDividend) {
    // Sin dividendo, la cobertura y la trayectoria no tienen nada que juzgar —
    // pero la calidad de la caja sí, y es justo lo que se estaba perdiendo.
    const quality = BLOCKS.find((block) => block.key === 'quality');
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        <DegradedPanel
          title="Sin dividendo que juzgar"
          reason="Esta empresa no registra dividendos pagados en la serie, así que no hay política de dividendo, cobertura ni trayectoria que evaluar."
          consequence="La calidad de la caja sí se calcula y se muestra debajo: mide si el beneficio se convierte en caja, que no depende de que se reparta o no."
        >
          <div style={{ marginTop: spacing.md }}>
            <FlagList flags={dividend.flags ?? []} emptyLabel="Sin banderas de dividendo." />
          </div>
        </DegradedPanel>
        {quality ? (
          <Card>
            <CardTitle size="sm">{quality.label}</CardTitle>
            <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
              <InlineNotice>{quality.note}</InlineNotice>
              <YearMatrix
                marksLegend={REPORT_LEGEND}
                highlightKey={highlightKey}
                years={years}
                rows={[...quality.metrics].map((key) => metricRow(key, options))}
                verdictYear={verdictYear}
                firstColumnLabel="Métrica"
              />
            </div>
          </Card>
        ) : null}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      {isFinancial ? (
        <InlineNotice>
          Esta empresa es una <strong>financiera</strong>. Las ratios que dividen por caja libre (D2
          a D5 y el margen de seguridad) salen sin calcular a propósito: en un banco esa caja libre
          no significa lo que significa en una industrial. El payout sobre beneficio, la calidad de
          la caja y la trayectoria del dividendo sí son válidos y se muestran.
        </InlineNotice>
      ) : null}
      {BLOCKS.map((block) => (
        <Card key={block.key}>
          <CardTitle size="sm">{block.label}</CardTitle>
          <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
            <InlineNotice>{block.note}</InlineNotice>
            <YearMatrix
              marksLegend={REPORT_LEGEND}
              highlightKey={highlightKey}
              years={years}
              rows={[...block.metrics].map((key) => metricRow(key, options))}
              verdictYear={verdictYear}
              firstColumnLabel="Métrica"
            />
          </div>
        </Card>
      ))}

      <Card>
        <CardTitle size="sm">Trayectoria</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <div style={{ display: 'flex', gap: spacing.lg, flexWrap: 'wrap' }}>
            <Stat
              label="Años seguidos sin recortar"
              value={String(dividend.trajectory?.streak_no_cut ?? 0)}
              hint="Es una cota inferior: se cuenta sobre los ejercicios ingeridos, no sobre el histórico completo de la empresa."
            />
            <Stat
              label="¿Se está frenando el crecimiento?"
              value={dividend.trajectory?.momentum_slowdown ? 'Sí' : 'No'}
              hint="Compara el crecimiento reciente del dividendo con el compuesto de toda la serie."
            />
          </div>
          <YearMatrix
            marksLegend={REPORT_LEGEND}
            highlightKey={highlightKey}
            years={years}
            rows={[dpsRow(run), metricRow('T2', options), metricRow('T3', options)]}
            firstColumnLabel="Concepto"
            legend="El CAGR y la estabilidad del payout se calculan una sola vez sobre toda la serie; por eso sólo tienen valor en la última columna."
          />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Banderas del dividendo</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <FlagList
            flags={dividend.flags ?? []}
            emptyLabel="Ninguna bandera de dividendo encendida."
          />
        </div>
      </Card>
    </div>
  );
}

function dpsRow(run: AnalysisRun): MatrixRow {
  const points = run.dividend_analysis.dps_series ?? [];
  return {
    key: 'dps',
    label: 'Dividendo por acción',
    cells: run.years_covered.map((year) => {
      const point = points.find((p) => p.fiscal_year === year);
      return { text: formatMetricValue(point?.dps ?? null, 'currency_per_share') };
    }),
  };
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 320 }}>
      <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>{label}</span>
      <span style={{ color: colors.text, fontSize: fontSize.lg, fontWeight: fontWeight.bold }}>
        {value}
      </span>
      <span style={{ color: colors.textSubtle, fontSize: fontSize.xs, lineHeight: 1.5 }}>
        {hint}
      </span>
    </div>
  );
}
