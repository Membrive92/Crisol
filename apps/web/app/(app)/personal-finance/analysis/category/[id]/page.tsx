'use client';

import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  useCategoryAvailablePeriods,
  useCategoryDetail,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  layout,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';
import { KpiCard } from '@/components/ui/kpi-card';
import {
  TimeSelector,
  type TimeSelectorRange,
} from '@/components/ui/time-selector';

/**
 * PHASE-25 — Drill-down de una categoría. Muestra KPIs (total, count,
 * ticket medio), evolución mensual y top 10 transacciones del rango.
 * Aterrizamos aquí desde el "Desglose de gastos" del análisis.
 */
export default function CategoryDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const searchParams = useSearchParams();
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

  // Rango inicial: si venimos del desglose de Análisis, hereda su periodo
  // (query `?from&to`) para no perder el mes/trimestre que el usuario tenía
  // activo. Sin esos params, default al año actual entero. El TimeSelector
  // deja saltar a otro mes o limpiar el filtro.
  //
  // AUDIT-2026-07-13 (#1): los límites del default se construyen en UTC
  // (`Date.UTC`), igual que `pickYear`/`pickMonth` del TimeSelector y
  // `boundsForAnchor`. Antes usaba `new Date(año, mes, día)` en hora LOCAL y
  // emitía `toISOString()`: en Europe/Madrid, `new Date(2026, 0, 1)` →
  // `2025-12-31T23:00:00Z`, así que `inferActiveRange` (que lee en UTC)
  // detectaba el año como 2025 y "rango personalizado" → el chip del año no
  // se marcaba y la barra de meses salía vacía ("Sin meses con datos en 2025").
  const [range, setRange] = useState<TimeSelectorRange>(() => {
    const from = searchParams?.get('from');
    const to = searchParams?.get('to');
    if (from && to) return { dateFrom: from, dateTo: to };
    const year = new Date().getFullYear();
    const start = new Date(Date.UTC(year, 0, 1, 0, 0, 0));
    const end = new Date(Date.UTC(year, 11, 31, 23, 59, 59));
    return { dateFrom: start.toISOString(), dateTo: end.toISOString() };
  });

  const { data: availablePeriods = [] } = useCategoryAvailablePeriods(id);

  // Construimos la query del backend sólo con los campos definidos
  // (TS strict no admite `undefined` explícito en props opcionales).
  const query = {
    ...(convertAll ? { target_currency: currency } : { currency }),
    ...(range.dateFrom ? { date_from: range.dateFrom } : {}),
    ...(range.dateTo ? { date_to: range.dateTo } : {}),
  };

  const { data, isLoading, isError, error } = useCategoryDetail(id, query);

  // PHASE-41 — "← Análisis" vuelve restaurando el período/filtro que traía el
  // desglose (query `?back=period&anchor&filter`), no al default anual.
  const backParams = searchParams?.get('back');
  const backHref = `/personal-finance/analysis${backParams ? `?${backParams}` : ''}`;

  if (!id) {
    return (
      <div style={{ padding: spacing.lg }}>
        <p style={{ color: colors.danger }}>ID de categoría inválido.</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      <Link
        href={backHref as never}
        style={{
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textDecoration: 'none',
        }}
      >
        ← Análisis
      </Link>

      <header
        style={{
          marginTop: spacing.sm,
          marginBottom: spacing.md,
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '1 1 360px', minWidth: 0 }}>
          {data ? (
            <>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: fontWeight.semibold,
                  color: colors.primary,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  display: 'block',
                  marginBottom: spacing.xs,
                }}
              >
                Categoría · {data.category_kind === 'income' ? 'Ingreso' : 'Gasto'}
              </span>
              <h1
                style={{
                  margin: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: spacing.sm,
                  fontSize: fontSize.xxl,
                  fontWeight: fontWeight.bold,
                  color: colors.text,
                  letterSpacing: '-0.02em',
                  lineHeight: 1.1,
                }}
              >
                {data.category_icon ? (
                  <span
                    aria-hidden
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: radius.md,
                      backgroundColor:
                        data.category_color ?? colors.surfaceMuted,
                      color: colors.onPrimary,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: fontSize.lg,
                    }}
                  >
                    {data.category_icon}
                  </span>
                ) : null}
                {data.category_name}
              </h1>
            </>
          ) : (
            <h1
              style={{
                margin: 0,
                fontSize: fontSize.xxl,
                fontWeight: fontWeight.bold,
                color: colors.text,
              }}
            >
              Cargando…
            </h1>
          )}
        </div>
      </header>

      <div style={{ marginBottom: spacing.lg }}>
        <TimeSelector
          availablePeriods={availablePeriods}
          value={range}
          onChange={setRange}
        />
      </div>

      {isError ? (
        <Card style={{ padding: spacing.lg }}>
          <p style={{ margin: 0, color: colors.danger, fontSize: fontSize.sm }}>
            Error al cargar la categoría:{' '}
            {error instanceof Error ? error.message : 'desconocido'}
          </p>
        </Card>
      ) : isLoading || !data ? (
        <Card style={{ padding: spacing.lg }}>
          <p style={{ margin: 0, color: colors.textMuted }}>Cargando…</p>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
          <section
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: spacing.md,
            }}
          >
            <KpiCard
              label="Total del periodo"
              value={formatAmount(data.total, data.currency)}
              valueColor={
                data.category_kind === 'income' ? colors.income : colors.expense
              }
            />
            <KpiCard label="Movimientos" value={String(data.count)} />
            <KpiCard
              label="Ticket medio"
              value={formatAmount(data.average_amount, data.currency)}
            />
          </section>

          <Card style={{ padding: spacing.lg }}>
            <header
              style={{
                marginBottom: spacing.md,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: fontSize.lg,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                }}
              >
                Evolución mensual
              </h2>
              <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
                Últimos 12 meses (independiente del periodo)
              </span>
            </header>
            {data.by_month.length === 0 ? (
              <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
                Sin actividad histórica para esta categoría.
              </p>
            ) : (
              <div style={{ width: '100%', height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={data.by_month.map((b) => ({
                      month: b.month,
                      monthLabel: spanishMonthLabel(b.month),
                      total: Number(b.total),
                    }))}
                    margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke={colors.border}
                      vertical={false}
                    />
                    <XAxis
                      dataKey="monthLabel"
                      tick={{ fill: colors.textMuted, fontSize: 11, fontWeight: 500 }}
                      axisLine={{ stroke: colors.border }}
                      tickLine={false}
                      interval="preserveStartEnd"
                      minTickGap={16}
                    />
                    <YAxis
                      tickFormatter={(v: number) =>
                        formatCompact(v, data.currency)
                      }
                      tick={{ fill: colors.textMuted, fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={72}
                    />
                    <Tooltip
                      cursor={{ stroke: colors.border, strokeDasharray: '2 2' }}
                      formatter={(v) =>
                        formatAmount(
                          String(Number(v ?? 0).toFixed(2)),
                          data.currency,
                        )
                      }
                      contentStyle={{
                        backgroundColor: colors.surface,
                        border: `1px solid ${colors.border}`,
                        borderRadius: radius.sm,
                        color: colors.text,
                      }}
                      labelStyle={{ color: colors.textMuted, fontSize: 11 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="total"
                      name="Total"
                      stroke={data.category_color ?? colors.primary}
                      strokeWidth={2.5}
                      dot={{
                        r: 3,
                        fill: data.category_color ?? colors.primary,
                        strokeWidth: 0,
                      }}
                      activeDot={{
                        r: 5,
                        fill: data.category_color ?? colors.primary,
                        strokeWidth: 0,
                      }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <Card style={{ padding: 0, overflow: 'hidden' }}>
            <div
              style={{
                padding: `${spacing.sm}px ${spacing.md}px`,
                borderBottom: `1px solid ${colors.border}`,
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                }}
              >
                Top movimientos · {data.top_transactions.length}
              </h2>
            </div>
            {data.top_transactions.length === 0 ? (
              <p
                style={{
                  margin: 0,
                  padding: spacing.lg,
                  color: colors.textMuted,
                  fontSize: fontSize.sm,
                  textAlign: 'center',
                }}
              >
                Sin movimientos en el periodo.
              </p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: colors.surfaceMuted }}>
                    <Th>Fecha</Th>
                    <Th>Descripción</Th>
                    <Th align="right">Importe</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_transactions.map((tx) => (
                    <tr key={tx.transaction_id}>
                      <Td>{formatDate(tx.occurred_at)}</Td>
                      <Td>
                        <Link
                          href={
                            `/personal-finance/transactions/${tx.transaction_id}` as never
                          }
                          style={{
                            color: colors.text,
                            textDecoration: 'none',
                            borderBottom: `1px dashed ${colors.borderStrong}`,
                          }}
                        >
                          {tx.description ?? '(sin descripción)'}
                        </Link>
                      </Td>
                      <Td align="right">
                        {formatAmount(tx.amount, data.currency)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

function Th({
  children,
  align = 'left',
}: {
  children: React.ReactNode;
  align?: 'left' | 'right';
}) {
  return (
    <th
      style={{
        textAlign: align,
        padding: `${spacing.sm}px ${spacing.md}px`,
        borderBottom: `1px solid ${colors.border}`,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        color: colors.textMuted,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align = 'left',
}: {
  children: React.ReactNode;
  align?: 'left' | 'right';
}) {
  return (
    <td
      style={{
        textAlign: align,
        padding: `${spacing.sm}px ${spacing.md}px`,
        borderBottom: `1px solid ${colors.border}`,
        color: colors.text,
        fontVariantNumeric: 'tabular-nums',
        fontSize: fontSize.sm,
      }}
    >
      {children}
    </td>
  );
}

const SPANISH_MONTHS = [
  'Ene',
  'Feb',
  'Mar',
  'Abr',
  'May',
  'Jun',
  'Jul',
  'Ago',
  'Sep',
  'Oct',
  'Nov',
  'Dic',
];

function spanishMonthLabel(month: string): string {
  const idx = parseInt(month.slice(5, 7), 10) - 1;
  return SPANISH_MONTHS[idx] ?? month;
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
