'use client';

import { colors, fontSize, FORENSIC_KEYS, spacing } from '@crisol/ui';
import type { AnalysisRun, Security } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { metricRow, type MetricRowOptions } from '@crisol/ui';
import type { CatalogIndex, MetricIndex } from '@crisol/ui';
import { ScoreBreakdownCard } from './score-breakdown-card';
import { YearMatrix } from './year-matrix';

export interface TabForensicProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  security: Security | undefined;
}

/**
 * La capa que el cuaderno del usuario no tiene: modelos publicados de detección
 * de manipulación contable y de riesgo de quiebra, todos *book-based* (ninguno
 * depende de la cotización, para que un análisis viejo se pueda reejecutar).
 */
export function TabForensic({ run, index, catalog, security }: TabForensicProps) {
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

  const breakdownFor = (key: string) =>
    (forensic.breakdowns ?? []).find(
      (b) => b.key === key && b.fiscal_year === verdictYear,
    );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <InlineNotice>
        Todos estos modelos son <strong>book-based</strong>: se calculan sólo con las cuentas
        publicadas, nunca con la cotización. Es lo que hace que reejecutar un análisis antiguo
        devuelva el mismo resultado.
      </InlineNotice>

      <Card>
        <CardTitle size="sm">Los ocho scores en el último ejercicio ({verdictYear})</CardTitle>
        <div
          style={{
            marginTop: spacing.md,
            display: 'grid',
            gap: spacing.md,
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))',
          }}
        >
          {FORENSIC_KEYS.map((key) => (
            <ScoreBreakdownCard
              key={key}
              metricKey={key}
              metric={verdictYear === undefined ? undefined : index.get(key, verdictYear)}
              breakdown={breakdownFor(key)}
              catalog={catalog}
              thresholdsUsed={run.thresholds_used}
              variant={key === 'z_score' ? run.z_variant : undefined}
            />
          ))}
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Evolución de los scores</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <YearMatrix
            years={years}
            rows={FORENSIC_KEYS.map((key) => metricRow(key, options))}
            verdictYear={verdictYear}
            firstColumnLabel="Score"
            legend={
              <p style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs }}>
                El primer ejercicio de la serie sale sin M-Score ni F-Score: ambos comparan
                contra el año anterior, y no lo hay.
              </p>
            }
          />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">Banderas forenses</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <FlagList
            flags={forensic.flags ?? []}
            emptyLabel="Ninguna bandera forense encendida."
          />
        </div>
      </Card>
    </div>
  );
}
