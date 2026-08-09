'use client';

import { colors, fontSize, spacing } from '@crisol/ui';
import type { AnalysisRun } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

import { CommonSizeDrift } from './common-size-drift';
import { DeltaHeatmap } from './delta-heatmap';
import { InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { formatMetricValue, formatPercentDelta } from '@crisol/ui';
import { metricRow, type MetricRowOptions } from '@crisol/ui';
import type { CatalogIndex, MetricIndex } from '@crisol/ui';
import { YearMatrix, type MatrixRow } from './year-matrix';

export interface TabEvolutionProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
}

/**
 * La pestaña que convierte los «Vigilar» del cuaderno en algo computable.
 *
 * Inventarios contra ventas, ventas planas, dilución… el cuaderno los enuncia
 * como cosas a mirar; el motor los tiene como cruces (C1-C8) que saltan solos.
 */
export function TabEvolution({ run, index, catalog }: TabEvolutionProps) {
  const evolution = run.evolution;
  const series = evolution.horizontal ?? [];
  const years = run.years_covered;
  const options: MetricRowOptions = { index, catalog, thresholdsUsed: run.thresholds_used };

  const seriesRows: MatrixRow[] = series.map((serie) => ({
    key: serie.key,
    label: serie.label,
    hint: serie.cagr
      ? `crecimiento compuesto ${formatPercentDelta(serie.cagr)} anual`
      : (serie.cagr_reason ?? 'sin crecimiento compuesto calculable'),
    cells: years.map((year) => {
      const point = serie.points.find((p) => p.fiscal_year === year);
      if (!point) return { text: '—' };
      return {
        text: formatMetricValue(point.value, undefined),
        title: point.yoy ? `variación ${formatPercentDelta(point.yoy)}` : undefined,
      };
    }),
  }));


  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card>
        <CardTitle size="sm">Las magnitudes, año a año</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <InlineNotice>
            La <strong>caja libre de mantenimiento</strong> descuenta sólo la inversión de
            reposición (el mínimo entre el capex y la amortización), no el capex entero: es la que
            tu cuaderno marca como recomendada frente a la puritana, porque no castiga a una
            empresa por invertir en crecer. Al ser una estimación —el desglose no se publica— va
            marcada como tal. El <strong>circulante operativo</strong> es tu working capital:
            existencias más cobros menos pagos, sin efectivo.
          </InlineNotice>
          <YearMatrix years={years} rows={seriesRows} firstColumnLabel="Magnitud" />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Variación interanual</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <InlineNotice>
            La misma tabla de antes, con el color como refuerzo: diez magnitudes por cinco
            ejercicios son cincuenta números que hay que leer uno a uno para ver el patrón. El
            número sigue impreso en cada celda a propósito —el verde y el rojo de la escala son
            indistinguibles para una de cada doce personas—, así que el color añade velocidad sin
            ser nunca la única fuente.
          </InlineNotice>
          <DeltaHeatmap series={series} years={years} />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Deriva de la estructura de márgenes</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <CommonSizeDrift vertical={evolution.vertical ?? []} />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Estabilidad y crecimiento</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <InlineNotice>
            La estabilidad del margen mide predictibilidad, y la predictibilidad ES seguridad: un
            margen errático convierte cualquier cobertura de dividendo en una lotería. El
            crecimiento sostenible es lo que la empresa puede crecer autofinanciándose; si el
            real lo supera de forma sostenida, el crecimiento se está pagando fuera.
          </InlineNotice>
          <YearMatrix
            years={years}
            rows={[metricRow('E3', options), metricRow('E4', options)]}
            firstColumnLabel="Métrica"
          />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Cruces detectados</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <p
            style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.6 }}
          >
            Aquí es donde viven los «Vigilar» de tu cuaderno: cobros creciendo por encima de las
            ventas, inventario que se acumula, dilución sostenida, retorno al accionista pagado
            con deuda.
          </p>
          <FlagList
            flags={evolution.flags ?? []}
            emptyLabel="Ningún cruce evolutivo ha saltado en esta serie."
          />
        </div>
      </Card>
    </div>
  );
}
