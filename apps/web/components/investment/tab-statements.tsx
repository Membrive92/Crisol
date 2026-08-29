'use client';

import { REPORT_LEGEND, spacing } from '@crisol/ui';
import type {
  AnalysisRun,
  CanonicalItemDefinition,
  FinancialStatement,
  StatementKind,
} from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import {
  buildStatementRows,
  collectQualityFlags,
  QUALITY_LABEL,
  type StatementViewMode,
} from '@crisol/ui';
import { YearMatrix } from './year-matrix';

type ViewMode = StatementViewMode;

export interface TabStatementsProps {
  run: AnalysisRun;
  statements: FinancialStatement[] | undefined;
  items: CanonicalItemDefinition[] | undefined;
  currency: string;
  sub: string;
  onSubChange: (key: string) => void;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export function TabStatements({
  run,
  statements,
  items,
  currency,
  sub,
  onSubChange,
  view,
  onViewChange,
}: TabStatementsProps) {
  if (!statements || statements.length === 0 || !items) {
    return (
      <DegradedPanel
        title="Sin estados financieros"
        reason="No hay ejercicios ingeridos para este valor, o el catálogo de partidas no se ha podido cargar."
      />
    );
  }

  const kind: StatementKind = sub === 'income' || sub === 'cashflow' ? sub : 'balance';
  const years = statements.map((s) => s.fiscal_year);
  const verdictYear = run.years_covered[run.years_covered.length - 1];

  const rows = buildStatementRows({ kind, items, statements, view, run });
  const qualityFlags = collectQualityFlags(statements);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          flexWrap: 'wrap',
          justifyContent: 'space-between',
        }}
      >
        <Segmented
          label="Estado financiero"
          value={kind}
          onChange={onSubChange}
          options={[
            { key: 'balance', label: 'Balance' },
            { key: 'income', label: 'Cuenta de resultados' },
            { key: 'cashflow', label: 'Flujo de caja' },
          ]}
        />
        <Segmented
          label="Modo de lectura"
          size="sm"
          value={view}
          onChange={(key) => onViewChange(key as ViewMode)}
          options={[
            { key: 'amount', label: `Millones ${currency}` },
            { key: 'weight', label: '% común' },
            { key: 'delta', label: 'Variación' },
          ]}
        />
      </div>

      {qualityFlags.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
          {qualityFlags.map((flag) => (
            <InlineNotice key={flag.key}>
              <strong>{flag.years.join(', ')}</strong> — {QUALITY_LABEL[flag.key] ?? flag.key}
            </InlineNotice>
          ))}
        </div>
      ) : null}

      {view === 'weight' && kind === 'cashflow' ? (
        <InlineNotice>
          El motor no calcula porcentaje común del flujo de caja: no hay una base contable única
          contra la que medir sus partidas. Cambia a millones o a variación.
        </InlineNotice>
      ) : null}
      {view === 'weight' && kind === 'income' ? (
        <InlineNotice>
          El porcentaje común de la cuenta de resultados cubre 12 de las 16 partidas: quedan fuera
          el resultado antes de impuestos y los tres recuentos de acciones.
        </InlineNotice>
      ) : null}

      <Card>
        <CardTitle size="sm">
          {kind === 'balance'
            ? 'Balance'
            : kind === 'income'
              ? 'Cuenta de resultados'
              : 'Flujo de caja'}
        </CardTitle>
        <div style={{ marginTop: spacing.md }}>
          <YearMatrix
            marksLegend={REPORT_LEGEND}
            years={years}
            rows={rows}
            verdictYear={verdictYear}
            firstColumnLabel="Partida"
            legend={
              <div>
                Un hueco en un estado es <strong>ausencia</strong> en el filing, no un cero: si el
                emisor no publica el concepto, la app no se lo inventa.
              </div>
            }
          />
        </div>
      </Card>
    </div>
  );
}
