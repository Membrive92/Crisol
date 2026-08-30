'use client';

import {
  colors,
  fontSize,
  FORENSIC_KEYS,
  FORENSIC_ROWS,
  REPORT_LEGEND,
  spacing,
} from '@crisol/ui';
import type { AnalysisRun, Security } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { metricGapLegend, metricRow, type MetricRowOptions } from '@crisol/ui';
import type { CatalogIndex, MetricIndex, ScoreHelpIndex } from '@crisol/ui';
import { ScoreBreakdownCard } from './score-breakdown-card';
import { YearMatrix } from './year-matrix';

export interface TabForensicProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  security: Security | undefined;
  /** Fichas de los scores y nombres de sus variables (PHASE-44.24.A). */
  help?: ScoreHelpIndex | undefined;
  /** Fila a la que se ha llegado desde el veredicto (PHASE-44.24.C.4). */
  highlightKey?: string | undefined;
}

/**
 * La capa que el cuaderno del usuario no tiene: modelos publicados de detección
 * de manipulación contable y de riesgo de quiebra, todos *book-based* (ninguno
 * depende de la cotización, para que un análisis viejo se pueda reejecutar).
 */
export function TabForensic({
  run,
  index,
  catalog,
  security,
  help,
  highlightKey,
}: TabForensicProps) {
  const forensic = run.scores_detail.forensic;
  const years = run.years_covered;
  const verdictYear = years[years.length - 1];
  const options: MetricRowOptions = { index, catalog, thresholdsUsed: run.thresholds_used };

  if (security?.is_financial) {
    return (
      <DegradedPanel
        title="Los modelos forenses no aplican a una financiera"
        reason="Beneish, Altman, Piotroski y compañía se calibraron sobre empresas no financieras. Un banco tiene un balance de otra naturaleza —el apalancamiento ES el negocio— y aplicarles estos cortes daría alarmas constantes sin significado."
        consequence="Consecuencia sobre el resto del informe: sin ningún score forense en verde, el perfil de seguridad no puede llegar a «Conservador», y la pregunta sobre la contabilidad se queda sin señales que evaluar."
      />
    );
  }

  // Derivada del run, no escrita a mano. La leyenda anterior afirmaba que sólo
  // el primer ejercicio se queda sin M-Score ni F-Score «porque comparan contra
  // el año anterior»: cierto en la empresa que su autor tenía delante, falso en
  // McDonald's, que se queda sin M-Score en los cinco ejercicios por una razón
  // distinta (no publica coste de ventas anual).
  const gaps = metricGapLegend(FORENSIC_KEYS, { index, catalog });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <InlineNotice>
        Todos estos modelos son <strong>book-based</strong>: se calculan sólo con las cuentas
        publicadas, nunca con la cotización. Es lo que hace que reejecutar un análisis antiguo
        devuelva el mismo resultado.
      </InlineNotice>

      <Card>
        <CardTitle size="sm">Los scores en el último ejercicio ({verdictYear})</CardTitle>
        <div
          style={{
            marginTop: spacing.md,
            display: 'grid',
            gap: spacing.md,
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))',
          }}
        >
          {FORENSIC_ROWS.map((row) => (
            <ScoreBreakdownCard
              key={row.key}
              metricKey={row.key}
              metric={verdictYear === undefined ? undefined : index.get(row.key, verdictYear)}
              breakdowns={forensic.breakdowns}
              year={verdictYear}
              index={index}
              catalog={catalog}
              thresholdsUsed={run.thresholds_used}
              variant={row.key === 'z_score' ? run.z_variant : undefined}
              help={help}
              {...(row.reading ? { readingKey: row.reading } : {})}
            />
          ))}
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Evolución de los scores</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <YearMatrix
            marksLegend={REPORT_LEGEND}
            highlightKey={highlightKey}
            years={years}
            rows={FORENSIC_ROWS.map((row) => metricRow(row.key, options))}
            verdictYear={verdictYear}
            firstColumnLabel="Score"
            legend={
              gaps.length === 0 ? undefined : (
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: spacing.lg,
                    color: colors.textSubtle,
                    fontSize: fontSize.xs,
                  }}
                >
                  {gaps.map((sentence) => (
                    <li key={sentence}>{sentence}</li>
                  ))}
                </ul>
              )
            }
          />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Banderas forenses</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <FlagList flags={forensic.flags ?? []} emptyLabel="Ninguna bandera forense encendida." />
        </div>
      </Card>
    </div>
  );
}
