'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { MonthlyBucket } from '@crisol/types';
import {
  SHORT_MONTHS_ES,
  colors,
  dayRangeLabel,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
  cycleRangeLabel,
} from '@crisol/ui';
import { cycleDaysForAnchor } from '@crisol/services';

import { Card, CardTitle } from '@/components/ui/card';
import type { PeriodKey } from './stitch-period-toggle';

// Etiquetas del eje X, derivadas de la tabla compartida (`@crisol/ui`) en vez
// de una copia propia: así el mes se escribe igual aquí, en el titular del
// período y en el chart de móvil.
const SHORT_MONTHS = SHORT_MONTHS_ES.map((m) => `${m.charAt(0).toUpperCase()}${m.slice(1)}`);

const PERIOD_NAMES: Record<PeriodKey, string> = {
  month: 'Mes',
  year: 'Año',
  custom: 'Personalizado',
};

export interface StitchIncomeVsExpensesProps {
  data: MonthlyBucket[];
  currency: string;
  isLoading: boolean;
  /**
   * Día en que empieza el mes del usuario. NO cambia la etiqueta de la barra
   * —el período se llama por el mes que lo ABRE— sino que añade el RANGO al
   * tooltip.
   *
   * Existe por un caso concreto: con corte el 12, la primera barra del año es
   * el período 12-dic → 11-ene, y para quien no tenía movimientos en diciembre
   * contiene sólo la cola de enero. La barra se lee «Dic 25» y el usuario ve un
   * año que nunca cargó. El dato es correcto; lo que faltaba era decir qué
   * abarca.
   */
  cycleStartDay?: number | undefined;
  /**
   * AUDIT-2026-07 — período y mes ancla navegados. En `month`/`year` el chart
   * pinta los 12 meses del año y RESALTA los del período activo (atenúa el
   * resto) para que togglear produzca un cambio visible.
   *
   * PHASE-41 — En `custom` NO se pinta la desagregación mensual (un rango
   * arbitrario parte en meses parciales y confunde): se muestran los TOTALES
   * REALES del rango (Ingresos vs Gastos + Neto), que reconcilian con los KPIs
   * day-exact porque son la Σ de los mismos buckets ya acotados al rango.
   */
  period?: PeriodKey;
  anchorMonth?: string;
  /** PHASE-41 — rango libre activo (`YYYY-MM-DD`): alimenta el caption del período. */
  customFrom?: string;
  customTo?: string;
  /**
   * C4 — Día en que empieza el mes del usuario. Con `period === 'cycle'` cada
   * barra ES un ciclo, así que se etiqueta por su día de cobro («Ciclo del 14
   * mar») en vez de con el nombre del mes: los buckets siguen llegando como
   * `YYYY-MM`, pero ese `YYYY-MM` es el ANCLA del ciclo, no el mes natural.
   * Etiquetarlas «Mar» diría que la barra es marzo entero, que es exactamente
   * la confusión que esta feature existe para quitar.
   */
  /**
   * Al hacer clic en un mes del chart, se invoca con su `YYYY-MM` para que el
   * caller navegue a ese mes (fija el mes ancla + período mensual). Sin este
   * prop (o en `custom`, sin barras mensuales), el chart no es clicable.
   */
  onSelectMonth?: (month: string) => void;
}

/**
 * Meses (1-12) resaltados, sólo para `month`/`year`. `month` resalta el mes
 * ancla; `year` los 12.
 */
function activeMonthsFor(period: PeriodKey, anchorMonth: string): Set<number> {
  if (period === 'month') return new Set([Number(anchorMonth.split('-')[1])]);
  return new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
}

// El caption del rango libre (`15 may – 15 jun 2026`) sale de `dayRangeLabel`
// (`@crisol/ui`), la MISMA función que pinta el subtítulo del ciclo. Estaba
// escrita aquí como `fmtDay` + `customRangeCaption`, produciendo carácter a
// carácter la misma cadena que la del ciclo, y las dos se pintan en esta
// pantalla: dos copias que sólo se notan el día que alguien corrige una.

interface ChartRow {
  month: string;
  monthLabel: string;
  /** «12 dic – 11 ene», sólo con ciclo. */
  rangeLabel: string | null;
  income: number;
  expenses: number;
  active: boolean;
}

/**
 * Ingresos vs Gastos (PHASE-18.1). En `month`/`year` es un bar chart agrupado
 * por mes (Recharts); en `custom` (PHASE-41) es la comparación de TOTALES del
 * rango, que es lo que el usuario quiere ver de un periodo arbitrario.
 */
export function StitchIncomeVsExpenses({
  data,
  currency,
  isLoading,
  cycleStartDay,
  period,
  anchorMonth,
  customFrom,
  customTo,
  onSelectMonth,
}: StitchIncomeVsExpensesProps) {
  const isCustom = period === 'custom' && customFrom != null && customTo != null;

  // Totales del periodo = Σ de los buckets (ya acotados al rango en custom):
  // reconcilian al céntimo con los KPIs day-exact (mismo `date_from/date_to`).
  const totalIncome = data.reduce((sum, b) => sum + Number(b.income), 0);
  const totalExpenses = data.reduce((sum, b) => sum + Number(b.expenses), 0);

  // Sólo atenuamos en 'month' (resaltar el mes ancla dentro del año).
  const highlight = period === 'month' && anchorMonth != null;
  const activeMonths =
    period != null && anchorMonth != null ? activeMonthsFor(period, anchorMonth) : null;
  /*
   * PHASE-47 — las barras se llaman por su MES, tenga el usuario ciclo o no:
   * su «julio» va del 12 de julio al 11 de agosto si ése es su corte, pero
   * sigue llamándose julio. Aquí ponía «Ciclo del 12 jul», vocabulario nuevo
   * para un concepto que el usuario ya tenía nombrado.
   *
   * El año se añade SÓLO cuando la serie cruza dos: con el mes del usuario, la
   * vista anual arranca en el ciclo que abrió en diciembre del año anterior
   * (porque contiene los días 1..D−1 de enero), así que sin esto habría dos
   * barras «dic» indistinguibles en los extremos.
   */
  const years = new Set(data.map((b) => b.month.slice(0, 4)));
  const mainYear = data.length > 0 ? data[data.length - 1]!.month.slice(0, 4) : null;
  const chartData: ChartRow[] = data.map((b) => {
    const monthNum = parseInt(b.month.slice(5, 7), 10); // 1-12
    const short = SHORT_MONTHS[monthNum - 1] ?? b.month;
    const year = b.month.slice(0, 4);
    return {
      month: b.month,
      monthLabel:
        years.size > 1 && year !== mainYear ? `${short} ${year.slice(2)}` : short,
      rangeLabel: cycleStartDay
        ? (() => {
            const d = cycleDaysForAnchor(cycleStartDay, b.month);
            return cycleRangeLabel(d.fromDay, d.toDay);
          })()
        : null,
      income: Number(b.income),
      expenses: Number(b.expenses),
      active: activeMonths == null || activeMonths.has(monthNum),
    };
  });
  const empty =
    !isLoading && data.every((b) => Number(b.income) === 0 && Number(b.expenses) === 0);
  const dim = (row: ChartRow) => (highlight && !row.active ? 0.22 : 1);
  // Caption: en custom anuncia el rango exacto que resumen los totales; en month
  // el mes resaltado; en year/omitido (con barras clicables), invita a clicar.
  const customCaption =
    isCustom && customFrom != null && customTo != null
      ? dayRangeLabel(customFrom, customTo)
      : null;
  const periodCaption =
    highlight && period != null ? `Resaltado: ${PERIOD_NAMES[period]} navegado` : null;
  const caption =
    customCaption ?? periodCaption ?? (!isCustom && onSelectMonth ? 'Haz clic en un mes' : null);

  // Clic en una barra → navegar a ese mes. Usamos el ÍNDICE del dato (fiable,
  // igual que el donut) en vez del `activePayload` del chart, que no siempre
  // llega poblado. Ignoramos meses sin datos (columnas vacías de meses futuros).
  function handleBarClick(index: number): void {
    if (!onSelectMonth) return;
    const row = chartData[index];
    if (!row || (row.income === 0 && row.expenses === 0)) return;
    onSelectMonth(row.month);
  }

  return (
    <Card
      style={{
        padding: spacing.lg,
        // Sólo en custom: flex-column para que los totales se centren y rellenen
        // el alto cuando la card se estira junto a la de patrimonio (más alta).
        // En month/year la card sigue siendo un bloque normal (chart intacto).
        ...(isCustom ? { display: 'flex', flexDirection: 'column' as const } : {}),
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.lg,
        }}
      >
        <CardTitle>Ingresos vs Gastos</CardTitle>
        {caption ? (
          <span
            style={{
              fontSize: fontSize.xs,
              color: colors.textMuted,
              fontWeight: fontWeight.medium,
            }}
          >
            {caption}
          </span>
        ) : null}
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin datos en el periodo.
        </p>
      ) : isCustom ? (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}
        >
          <PeriodTotals income={totalIncome} expenses={totalExpenses} currency={currency} />
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
            barCategoryGap="20%"
            barGap={2}
            {...(onSelectMonth ? { style: { cursor: 'pointer' } } : {})}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
            <XAxis
              dataKey="monthLabel"
              tick={{ fontSize: 11, fill: colors.textMuted, fontWeight: 500 }}
              axisLine={{ stroke: colors.border }}
              tickLine={false}
              interval={0}
            />
            <YAxis
              tickFormatter={(v: number) => formatCompact(v, currency)}
              tick={{ fontSize: 11, fill: colors.textMuted }}
              axisLine={false}
              tickLine={false}
              width={64}
            />
            <Tooltip
              cursor={{ fill: colors.surfaceMuted, opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const firstRow = payload[0]?.payload as ChartRow | undefined;
                if (!firstRow) return null;
                const entries = payload.map((p) => ({
                  name: typeof p.name === 'string' ? p.name : String(p.name ?? ''),
                  value: typeof p.value === 'number' ? p.value : 0,
                  color: typeof p.color === 'string' ? p.color : colors.text,
                }));
                return (
                  <ComparisonTooltip
                    monthLabel={firstRow.monthLabel}
                    rangeLabel={firstRow.rangeLabel}
                    entries={entries}
                    currency={currency}
                  />
                );
              }}
              animationDuration={120}
            />
            <Legend
              wrapperStyle={{
                paddingTop: spacing.sm,
                fontSize: fontSize.xs,
                color: colors.textMuted,
              }}
              iconType="circle"
              iconSize={10}
            />
            <Bar
              dataKey="income"
              name="Ingresos"
              fill={colors.success}
              radius={[3, 3, 0, 0]}
              animationDuration={400}
              onClick={(_, index) => handleBarClick(index)}
            >
              {chartData.map((row) => (
                <Cell key={`inc-${row.month}`} fillOpacity={dim(row)} />
              ))}
            </Bar>
            <Bar
              dataKey="expenses"
              name="Gastos"
              fill={colors.danger}
              radius={[3, 3, 0, 0]}
              animationDuration={400}
              onClick={(_, index) => handleBarClick(index)}
            >
              {chartData.map((row) => (
                <Cell key={`exp-${row.month}`} fillOpacity={dim(row)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

interface PeriodTotalsProps {
  income: number;
  expenses: number;
  currency: string;
}

/**
 * PHASE-41 — Comparación de TOTALES del rango libre: dos barras proporcionales
 * (Ingresos / Gastos) + Neto. Es la vista de `custom`: muestra los ingresos y
 * gastos REALES del periodo sin la desagregación mensual (que en un rango
 * arbitrario parte en meses parciales y confunde).
 */
function PeriodTotals({ income, expenses, currency }: PeriodTotalsProps) {
  const net = income - expenses;
  const max = Math.max(income, expenses, 1);
  const rows = [
    { label: 'Ingresos', value: income, color: colors.success },
    { label: 'Gastos', value: expenses, color: colors.danger },
  ] as const;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {rows.map((r) => (
          <div key={r.label} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                fontSize: fontSize.sm,
              }}
            >
              <span style={{ color: colors.textMuted, fontWeight: fontWeight.medium }}>
                {r.label}
              </span>
              <span
                style={{
                  color: r.color,
                  fontWeight: fontWeight.semibold,
                  fontSize: fontSize.md,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatAmount(String(r.value.toFixed(2)), currency)}
              </span>
            </div>
            <div
              style={{
                height: 12,
                borderRadius: radius.sm,
                backgroundColor: colors.surfaceMuted,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${(r.value / max) * 100}%`,
                  minWidth: r.value > 0 ? 3 : 0,
                  backgroundColor: r.color,
                  borderRadius: radius.sm,
                  transition: 'width 300ms ease',
                }}
              />
            </div>
          </div>
        ))}
      </div>
      {/* Neto como bloque-resultado destacado (no una línea suelta). */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: `${spacing.sm}px ${spacing.md}px`,
          borderRadius: radius.md,
          backgroundColor: colors.surfaceMuted,
          border: `1px solid ${colors.border}`,
        }}
      >
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Neto del periodo
        </span>
        <span
          style={{
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: net >= 0 ? colors.income : colors.danger,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {net >= 0 ? '+' : ''}
          {formatAmount(String(net.toFixed(2)), currency)}
        </span>
      </div>
    </div>
  );
}

interface ComparisonTooltipProps {
  monthLabel: string;
  rangeLabel?: string | null;
  entries: readonly { name: string; value: number; color: string }[];
  currency: string;
}

function ComparisonTooltip({
  monthLabel,
  rangeLabel,
  entries,
  currency,
}: ComparisonTooltipProps) {
  // PHASE-29.6: añadimos línea "Neto" debajo, separada por un
  // border-top, con color según signo. Se calcula a partir de los
  // entries (income − expenses) sin asumir un orden concreto.
  const income = entries.find((e) => e.name === 'Ingresos')?.value ?? 0;
  const expenses = entries.find((e) => e.name === 'Gastos')?.value ?? 0;
  const net = income - expenses;
  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        minWidth: 160,
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
      }}
    >
      <div
        style={{ fontSize: 11, color: colors.textMuted, marginBottom: rangeLabel ? 0 : 4 }}
      >
        {monthLabel}
      </div>
      {/*
        * Qué abarca de verdad la barra. Con corte a mitad de mes todos los
        * períodos cruzan dos meses, y el nombre sólo dice cuál lo ABRE: sin
        * esto, la primera barra del año se lee «Dic 25» aunque todo su dinero
        * sea de enero.
        */}
      {rangeLabel ? (
        <div style={{ fontSize: 10, color: colors.textMuted, marginBottom: 4, opacity: 0.8 }}>
          {rangeLabel}
        </div>
      ) : null}
      {entries.map((entry) => (
        <div
          key={entry.name || String(entry.value)}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: entry.color,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          <span>{entry.name}</span>
          <span>{formatAmount(String(entry.value.toFixed(2)), currency)}</span>
        </div>
      ))}
      <div
        style={{
          marginTop: 4,
          paddingTop: 4,
          borderTop: `1px solid ${colors.border}`,
          display: 'flex',
          justifyContent: 'space-between',
          gap: spacing.sm,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: net >= 0 ? colors.income : colors.danger,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span>Neto</span>
        <span>
          {net >= 0 ? '+' : ''}
          {formatAmount(String(net.toFixed(2)), currency)}
        </span>
      </div>
    </div>
  );
}

function formatCompact(value: number, currency: string): string {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : currency;
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs === 0) return `0 ${symbol}`;
  if (abs < 1000) return `${sign}${Math.round(abs)} ${symbol}`;
  if (abs < 1_000_000) {
    const v = abs / 1000;
    return `${sign}${v.toFixed(v < 10 ? 1 : 0)}k ${symbol}`.replace('.', ',');
  }
  const v = abs / 1_000_000;
  return `${sign}${v.toFixed(v < 10 ? 1 : 0)}M ${symbol}`.replace('.', ',');
}
