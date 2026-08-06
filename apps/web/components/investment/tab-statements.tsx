'use client';

import { spacing } from '@crisol/ui';
import type {
  AnalysisRun,
  CanonicalItemDefinition,
  FinancialStatement,
  ItemGroup,
  StatementKind,
} from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { formatPercentDelta, formatStatementAmount, formatWeight } from './metric-format';
import { YearMatrix, type MatrixRow } from './year-matrix';

/** Etiquetas de los bloques, en el orden de lectura del cuaderno del usuario. */
const GROUP_LABEL: Record<ItemGroup, string> = {
  assets_current: 'Activo corriente',
  assets_noncurrent: 'Activo no corriente',
  liabilities_current: 'Pasivo corriente',
  liabilities_noncurrent: 'Pasivo no corriente',
  equity: 'Patrimonio neto',
  income_gross: 'Margen bruto',
  income_operating: 'Explotación (EBIT)',
  income_financial: 'Financiero',
  income_tax: 'Impuestos',
  income_result: 'Resultado',
  income_shares: 'Acciones',
  cashflow_operating: 'Actividades de explotación',
  cashflow_investing: 'Actividades de inversión',
  cashflow_financing: 'Actividades de financiación',
};

const GROUP_ORDER: ItemGroup[] = [
  'assets_current',
  'assets_noncurrent',
  'liabilities_current',
  'liabilities_noncurrent',
  'equity',
  'income_gross',
  'income_operating',
  'income_financial',
  'income_tax',
  'income_result',
  'income_shares',
  'cashflow_operating',
  'cashflow_investing',
  'cashflow_financing',
];

/** Las partidas que son un total de su bloque: se resaltan. */
const TOTALS = new Set([
  'current_assets',
  'total_assets',
  'current_liabilities',
  'total_liabilities',
  'equity',
  'ebit',
  'net_income',
  'cfo',
]);

/** Las banderas de calidad del dato que la ingesta deja en `raw_source_ref`.
 *  NO son banderas del engine: hablan del DATO, no del negocio. */
const QUALITY_LABEL: Record<string, string> = {
  balance_identity_unverifiable:
    'El cuadre del balance no es verificable: el pasivo total no venía en el filing y se dedujo restando el patrimonio del activo.',
  balance_identity_broken: 'El balance no cuadra: activo ≠ pasivo + patrimonio.',
  net_margin_out_of_range: 'El margen neto queda fuera del rango plausible.',
  components_exceed_total: 'La suma de los componentes supera su total.',
};

type ViewMode = 'amount' | 'weight' | 'delta';

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

  const rows = buildRows({ kind, items, statements, view, run });
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
          El porcentaje común de la cuenta de resultados cubre 12 de las 16 partidas: quedan
          fuera el resultado antes de impuestos y los tres recuentos de acciones.
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
            years={years}
            rows={rows}
            verdictYear={verdictYear}
            firstColumnLabel="Partida"
            legend={
              <>
                <div>
                  <strong>—</strong> hueco: el filing no publica el concepto. No es un cero.
                </div>
                <div>
                  <strong>·</strong> cero imputado · <strong>†</strong> derivada de otras
                  partidas · <strong>≈</strong> proxy estimado
                </div>
                <div>
                  <strong>•</strong> ejercicio que alimenta el dictamen
                </div>
              </>
            }
          />
        </div>
      </Card>
    </div>
  );
}

interface BuildRowsArgs {
  kind: StatementKind;
  items: CanonicalItemDefinition[];
  statements: FinancialStatement[];
  view: ViewMode;
  run: AnalysisRun;
}

function buildRows({ kind, items, statements, view, run }: BuildRowsArgs): MatrixRow[] {
  const relevant = items.filter((item) => item.statement === kind);
  const groups = GROUP_ORDER.filter((group) => relevant.some((item) => item.group === group));
  const rows: MatrixRow[] = [];

  for (const group of groups) {
    rows.push({ key: `group-${group}`, label: GROUP_LABEL[group], isGroup: true, cells: [] });
    for (const item of relevant.filter((i) => i.group === group)) {
      rows.push({
        key: item.key,
        label: item.label,
        hint: item.note || undefined,
        emphasis: TOTALS.has(item.key),
        cells: statements.map((statement) => cellFor(item, statement, view, run)),
      });
    }
  }
  return rows;
}

function cellFor(
  item: CanonicalItemDefinition,
  statement: FinancialStatement,
  view: ViewMode,
  run: AnalysisRun,
) {
  const raw = statement[item.key as keyof FinancialStatement];
  const value = typeof raw === 'string' || raw === null ? raw : null;

  if (view === 'weight') {
    const point = run.evolution.vertical.find(
      (p) => p.item === item.key && p.fiscal_year === statement.fiscal_year,
    );
    return point
      ? { text: formatWeight(point.weight), title: `sobre ${point.base}` }
      : { text: '—', title: 'esta partida no entra en el porcentaje común' };
  }

  if (view === 'delta') {
    const series = run.evolution.horizontal.find((s) => s.key === item.key);
    const point = series?.points.find((p) => p.fiscal_year === statement.fiscal_year);
    if (point) return { text: formatPercentDelta(point.yoy) };
    return { text: '—', title: 'sin serie interanual para esta partida' };
  }

  const provenance = provenanceOf(statement, item.key);
  return {
    text: formatStatementAmount(value),
    title:
      value === null ? 'el filing no publica este concepto (hueco, no cero)' : provenanceTitle(provenance),
    mark: provenanceMark(provenance),
  };
}

function provenanceOf(statement: FinancialStatement, key: string): string | null {
  const mapping = statement.raw_source_ref?.['mapping'];
  if (typeof mapping !== 'object' || mapping === null) return null;
  const trace = (mapping as Record<string, unknown>)[key];
  if (typeof trace !== 'object' || trace === null) return null;
  const provenance = (trace as Record<string, unknown>)['provenance'];
  return typeof provenance === 'string' ? provenance : null;
}

function provenanceMark(provenance: string | null): string | undefined {
  if (provenance === 'imputed_zero') return '·';
  if (provenance === 'derived') return '†';
  if (provenance === 'estimated') return '≈';
  return undefined;
}

function provenanceTitle(provenance: string | null): string | undefined {
  if (provenance === 'imputed_zero') return 'cero imputado: el filing no etiqueta el concepto';
  if (provenance === 'derived') return 'derivada por identidad contable, no publicada';
  if (provenance === 'estimated') return 'proxy estimado';
  return undefined;
}

function collectQualityFlags(
  statements: FinancialStatement[],
): { key: string; years: number[] }[] {
  const byKey = new Map<string, number[]>();
  for (const statement of statements) {
    const raw = statement.raw_source_ref?.['quality_flags'];
    if (!Array.isArray(raw)) continue;
    for (const entry of raw) {
      const key =
        typeof entry === 'string'
          ? entry
          : typeof entry === 'object' && entry !== null
            ? String((entry as Record<string, unknown>)['key'] ?? '')
            : '';
      if (!key) continue;
      const years = byKey.get(key) ?? [];
      years.push(statement.fiscal_year);
      byKey.set(key, years);
    }
  }
  return [...byKey.entries()].map(([key, years]) => ({ key, years }));
}
