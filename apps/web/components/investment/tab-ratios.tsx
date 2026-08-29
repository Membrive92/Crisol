'use client';

import {
  colors,
  DUPONT_SECTIONS,
  dupontCheckRow,
  fontSize,
  RATIO_FAMILIES,
  spacing,
  REPORT_LEGEND,
} from '@crisol/ui';
import type { AnalysisRun, DuPontDecomposition, MetricResult } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { groupRow, metricRow, missingRow, type MetricRowOptions } from '@crisol/ui';
import type { CatalogIndex, MetricIndex } from '@crisol/ui';
import { YearMatrix, type MatrixRow } from './year-matrix';

// Las familias y sus notas viven en `@crisol/ui` (PHASE-44.8): son CONTENIDO, y
// móvil debe enseñar exactamente las mismas métricas en cada bloque. Aquí sólo
// se le añade la pestaña DuPont, que no es una familia de métricas del catálogo
// sino una descomposición con su propia estructura.
const FAMILIES = [
  ...RATIO_FAMILIES,
  { key: 'dupont', label: 'DuPont', metrics: [] as readonly string[], note: '' },
] as const;

/** Lo que el cuaderno pide y el motor no calcula. Se lista en gris con motivo:
 *  omitirlo se leería como «no aplica», y lo que pasa es que no existe. */
const MISSING_BY_FAMILY: Record<string, { key: string; label: string; reason: string }[]> = {};

export interface TabRatiosProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  sub: string;
  onSubChange: (key: string) => void;
  /** Fila a la que se ha llegado desde el veredicto (PHASE-44.24.C.4). */
  highlightKey?: string | undefined;
}

export function TabRatios({ run, index, catalog, sub, onSubChange, highlightKey }: TabRatiosProps) {
  const years = run.years_covered;
  const verdictYear = years[years.length - 1];
  const options: MetricRowOptions = {
    index,
    catalog,
    thresholdsUsed: run.thresholds_used,
  };

  const family = FAMILIES.find((f) => f.key === sub) ?? FAMILIES[0];

  const segmentedOptions = FAMILIES.map((f) => {
    if (f.key === 'dupont') return { key: f.key, label: f.label };
    const computable = f.metrics.some((key) =>
      index.series(key).some((m) => m && m.status !== 'not_computable'),
    );
    return {
      key: f.key,
      label: f.label,
      degraded: !computable,
      degradedHint: 'ninguna métrica de este bloque es calculable con los datos de este valor',
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Segmented
        label="Familia de ratios"
        value={family.key}
        onChange={onSubChange}
        options={segmentedOptions}
      />

      {family.key === 'dupont' ? (
        <DuPontSection run={run} catalog={catalog} highlightKey={highlightKey} />
      ) : (
        <Card>
          <CardTitle size="sm">{family.label}</CardTitle>
          <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
            <InlineNotice>{family.note}</InlineNotice>
            <YearMatrix
              marksLegend={REPORT_LEGEND}
              highlightKey={highlightKey}
              years={years}
              rows={buildFamilyRows(family.key, [...family.metrics], options, years)}
              verdictYear={verdictYear}
              firstColumnLabel="Métrica"
              legend={
                <>
                  <div>
                    Cada corte sale del catálogo de umbrales del motor, calibrado por sector: el
                    mismo número puede ser verde en una eléctrica y rojo en una tecnológica.
                  </div>
                </>
              }
            />
          </div>
        </Card>
      )}
    </div>
  );
}

function buildFamilyRows(
  familyKey: string,
  metrics: string[],
  options: MetricRowOptions,
  years: number[],
): MatrixRow[] {
  const rows = metrics.map((key) => metricRow(key, options));
  const missing = MISSING_BY_FAMILY[familyKey] ?? [];
  if (missing.length === 0) return rows;
  return [
    ...rows,
    groupRow(`${familyKey}-missing`, 'Tu cuaderno lo pide y el motor no lo calcula'),
    ...missing.map((m) => missingRow(m.key, m.label, m.reason, years)),
  ];
}

function DuPontSection({
  run,
  catalog,
  highlightKey,
}: {
  run: AnalysisRun;
  catalog: CatalogIndex;
  highlightKey?: string | undefined;
}) {
  const dupont = run.scores_detail.base_ratios.dupont ?? [];
  if (dupont.length === 0) {
    return (
      <DegradedPanel
        title="Sin descomposición DuPont"
        reason="Este análisis no trae la descomposición del ROE. Vuelve a ejecutarlo para obtenerla."
      />
    );
  }

  const years = dupont.map((d) => d.fiscal_year);
  const pointFor = (year: number) => dupont.find((d) => d.fiscal_year === year);

  // Índice sobre la propia descomposición: sus MetricResult son los MISMOS
  // objetos que emite la capa 1, así que la fila de aquí y la de la matriz de
  // Rentabilidad no pueden divergir.
  // Los tres últimos son opcionales: el desdoble de cinco factores llegó en
  // PHASE-44.10 y un run anterior no los trae. `metricRow` los pinta con el
  // motivo correcto («no existía en la versión del motor…»), no como si a la
  // empresa le faltaran datos.
  const FACTORS: Record<string, (d: DuPontDecomposition) => MetricResult | undefined> = {
    R4: (d) => d.net_margin,
    A4: (d) => d.asset_turnover,
    DUPONT_EM: (d) => d.equity_multiplier,
    DUPONT_OM: (d) => d.operating_margin,
    DUPONT_TAX: (d) => d.tax_effect,
    DUPONT_FIN: (d) => d.financial_cost,
  };

  const options: MetricRowOptions = {
    index: {
      get: (key, year) => {
        const point = pointFor(year);
        const pick = FACTORS[key];
        return point && pick ? pick(point) : undefined;
      },
      series: (key) =>
        years.map((year) => {
          const point = pointFor(year);
          const pick = FACTORS[key];
          return point && pick ? pick(point) : undefined;
        }),
      years,
      keys: Object.keys(FACTORS),
    },
    catalog,
    thresholdsUsed: run.thresholds_used,
  };

  // Las dos tarjetas salen de `DUPONT_SECTIONS` (capa compartida) en vez de
  // estar escritas aquí: mientras lo estuvieron, móvil no tenía el DuPont y
  // nada avisaba — el test de paridad comparaba contra la lista compartida, que
  // es justo donde no estaba (PHASE-44.20).
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      {DUPONT_SECTIONS.map((section) => (
        <Card key={section.key}>
          <CardTitle size="sm">{section.label}</CardTitle>
          <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
            <p
              style={{
                margin: 0,
                color: colors.textMuted,
                fontSize: fontSize.sm,
                lineHeight: 1.6,
              }}
            >
              {section.note}
            </p>
            <YearMatrix
              marksLegend={REPORT_LEGEND}
              highlightKey={highlightKey}
              years={years}
              rows={[
                ...section.metrics.map((key) => metricRow(key, options)),
                dupontCheckRow(section.check, dupont, (d) => d[section.check]),
              ]}
              firstColumnLabel="Factor"
            />
          </div>
        </Card>
      ))}
    </div>
  );
}
