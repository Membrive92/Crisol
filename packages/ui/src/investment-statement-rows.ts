import type {
  AnalysisRun,
  CanonicalItemDefinition,
  FinancialStatement,
  ItemGroup,
  StatementKind,
} from '@crisol/types';

import { formatPercentDelta, formatStatementAmount, formatWeight } from './investment-metric-format';
import type { MatrixCell, MatrixRow } from './investment-matrix';

/**
 * Construcción de las filas de los estados financieros — capa PURA compartida
 * por web y móvil (PHASE-44.8).
 *
 * Lo que se comparte aquí no es cosmética: es qué partidas salen, en qué orden,
 * cuáles se resaltan como total, y —lo importante— **la marca de procedencia**.
 * Un `0` imputado y un `0` publicado se leen igual si nadie los distingue, y esa
 * distinción es la diferencia entre «esta empresa no tiene deuda» y «el filing
 * no etiqueta ese concepto». No puede depender de en qué pantalla lo mires.
 */

/** Etiquetas de los bloques, en el orden de lectura del cuaderno del usuario. */
export const GROUP_LABEL: Record<ItemGroup, string> = {
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

export const GROUP_ORDER: ItemGroup[] = [
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
export const TOTAL_ITEMS = new Set([
  'current_assets',
  'total_assets',
  'current_liabilities',
  'total_liabilities',
  'equity',
  'ebit',
  'net_income',
  'cfo',
]);

/**
 * Banderas de calidad del DATO que la ingesta deja en `raw_source_ref`.
 * NO son banderas del engine: hablan del dato, no del negocio.
 */
export const QUALITY_LABEL: Record<string, string> = {
  balance_identity_unverifiable:
    'El cuadre del balance no es verificable: el pasivo total no venía en el filing y se dedujo restando el patrimonio del activo.',
  balance_identity_broken: 'El balance no cuadra: activo ≠ pasivo + patrimonio.',
  net_margin_out_of_range: 'El margen neto queda fuera del rango plausible.',
  components_exceed_total: 'La suma de los componentes supera su total.',
  scale_incoherent: 'Una magnitud está en una escala incoherente con las demás.',
};

export type StatementViewMode = 'amount' | 'weight' | 'delta';

export interface StatementRowsArgs {
  kind: StatementKind;
  items: CanonicalItemDefinition[];
  statements: FinancialStatement[];
  view: StatementViewMode;
  run: AnalysisRun;
}

export function buildStatementRows({
  kind,
  items,
  statements,
  view,
  run,
}: StatementRowsArgs): MatrixRow[] {
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
        emphasis: TOTAL_ITEMS.has(item.key),
        cells: statements.map((statement) => statementCell(item, statement, view, run)),
      });
    }
  }
  return rows;
}

export function statementCell(
  item: CanonicalItemDefinition,
  statement: FinancialStatement,
  view: StatementViewMode,
  run: AnalysisRun,
): MatrixCell {
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
      value === null
        ? 'el filing no publica este concepto (hueco, no cero)'
        : provenanceTitle(provenance),
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

export function provenanceMark(provenance: string | null): string | undefined {
  if (provenance === 'imputed_zero') return '·';
  if (provenance === 'derived') return '†';
  if (provenance === 'estimated') return '≈';
  return undefined;
}

export function provenanceTitle(provenance: string | null): string | undefined {
  if (provenance === 'imputed_zero') return 'cero imputado: el filing no etiqueta el concepto';
  if (provenance === 'derived') return 'derivada por identidad contable, no publicada';
  if (provenance === 'estimated') return 'proxy estimado';
  return undefined;
}

export function collectQualityFlags(
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
