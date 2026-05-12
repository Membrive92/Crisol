'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo } from 'react';

import {
  formatApiError,
  useAccount,
  useAccountBalances,
  useAmortizationSchedule,
} from '@crisol/services';
import { colors, fontSize, fontWeight, formatAmount, formatDate, radius, spacing } from '@crisol/ui';

import { AccountSwatch } from '@/components/accounts/account-swatch';
import { Card } from '@/components/ui/card';
import { KpiCard } from '@/components/ui/kpi-card';

/**
 * Formatea un total de meses como "X años Y meses" o "Y meses" si <12.
 * Usado para el KPI de plazo restante.
 */
function formatMonthsAsDuration(months: number): string {
  if (months <= 0) return '—';
  const years = Math.floor(months / 12);
  const remainder = months - years * 12;
  if (years === 0) return `${remainder} ${remainder === 1 ? 'mes' : 'meses'}`;
  if (remainder === 0) return `${years} ${years === 1 ? 'año' : 'años'}`;
  return `${years} ${years === 1 ? 'año' : 'años'} ${remainder} ${remainder === 1 ? 'mes' : 'meses'}`;
}

/**
 * Cuenta cuántos meses han pasado entre `start_date` y la fecha actual.
 * Devuelve un valor en `[0, term_months]` — sin meses negativos ni
 * mayores que el plazo total.
 */
function monthsElapsedSince(startDate: string, totalMonths: number): number {
  const start = new Date(`${startDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime())) return 0;
  const now = new Date();
  const elapsed =
    (now.getFullYear() - start.getFullYear()) * 12 +
    (now.getMonth() - start.getMonth());
  if (elapsed < 0) return 0;
  if (elapsed > totalMonths) return totalMonths;
  return elapsed;
}

export default function AmortizationPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const accountQuery = useAccount(id);
  const scheduleQuery = useAmortizationSchedule(id);
  // Necesitamos `current_balance` para el "capital pendiente actual".
  // Pedimos balances en el mismo render — el resultado se cachea con
  // staleTime 60s y suele venir ya tibio desde otras pantallas.
  const balancesQuery = useAccountBalances();

  const account = accountQuery.data;
  const schedule = scheduleQuery.data;

  const balanceItem = useMemo(() => {
    if (!id) return undefined;
    return balancesQuery.data?.items.find((item) => item.account_id === id);
  }, [balancesQuery.data, id]);

  const isMissingFields = scheduleQuery.isError;

  if (!id) {
    return (
      <div style={{ padding: spacing.lg }}>
        <p style={{ color: colors.danger }}>ID de cuenta inválido.</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: spacing.lg }}>
      <Link
        href="/settings/accounts"
        style={{
          fontSize: fontSize.sm,
          color: colors.textMuted,
          textDecoration: 'none',
        }}
      >
        ← Cuentas
      </Link>

      <header
        style={{
          marginTop: spacing.sm,
          marginBottom: spacing.lg,
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
          flexWrap: 'wrap',
        }}
      >
        {account ? (
          <AccountSwatch color={account.color} icon={account.icon} size={44} />
        ) : null}
        <div style={{ flex: '1 1 280px', minWidth: 0 }}>
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
            Cuadro de amortización · Local
          </span>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xxl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.02em',
              lineHeight: 1.1,
            }}
          >
            {account?.name ?? 'Cuenta'}
          </h1>
          {balanceItem ? (
            <p
              style={{
                margin: `${spacing.xs}px 0 0 0`,
                color: colors.textMuted,
                fontSize: fontSize.sm,
              }}
            >
              Capital pendiente actual:{' '}
              <strong
                style={{
                  color: colors.danger,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatAmount(balanceItem.current_balance, balanceItem.currency)}
              </strong>
            </p>
          ) : null}
        </div>
      </header>

      {accountQuery.isLoading || scheduleQuery.isLoading ? (
        <Card style={{ padding: spacing.lg }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
            Cargando cuadro…
          </p>
        </Card>
      ) : isMissingFields ? (
        <EmptyState accountId={id} error={scheduleQuery.error} />
      ) : schedule ? (
        <AmortizationContent
          schedule={schedule}
          currency={account?.currency ?? 'EUR'}
        />
      ) : null}
    </div>
  );
}

function AmortizationContent({
  schedule,
  currency,
}: {
  schedule: NonNullable<ReturnType<typeof useAmortizationSchedule>['data']>;
  currency: string;
}) {
  const elapsed = monthsElapsedSince(schedule.start_date, schedule.term_months);
  const remainingMonths = Math.max(0, schedule.term_months - elapsed);
  const aprPercent = (Number(schedule.apr) * 100).toFixed(2);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: spacing.md,
        }}
      >
        <KpiCard
          label="Cuota mensual"
          value={formatAmount(schedule.monthly_payment, currency)}
        />
        <KpiCard
          label="Intereses totales"
          value={formatAmount(schedule.total_interest, currency)}
          valueColor={colors.danger}
        />
        <KpiCard
          label="Total a pagar"
          value={formatAmount(schedule.total_paid, currency)}
        />
        <KpiCard
          label="Plazo restante"
          value={formatMonthsAsDuration(remainingMonths)}
          footer={
            <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
              {schedule.term_months} meses totales · {aprPercent}% APR
            </span>
          }
        />
      </section>

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <div
          style={{
            padding: `${spacing.sm}px ${spacing.md}px`,
            borderBottom: `1px solid ${colors.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: spacing.md,
            flexWrap: 'wrap',
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
            Tabla completa · {schedule.rows.length} cuotas
          </h2>
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            Inicio: {formatDate(`${schedule.start_date}T00:00:00Z`)}
          </span>
        </div>
        <div
          style={{
            maxHeight: 540,
            overflow: 'auto',
            position: 'relative',
          }}
        >
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: fontSize.sm,
            }}
          >
            <thead>
              <tr
                style={{
                  position: 'sticky',
                  top: 0,
                  backgroundColor: colors.surface,
                  zIndex: 1,
                }}
              >
                <Th>Mes</Th>
                <Th>Fecha</Th>
                <Th align="right">Cuota</Th>
                <Th align="right">Intereses</Th>
                <Th align="right">Principal</Th>
                <Th align="right">Saldo pendiente</Th>
              </tr>
            </thead>
            <tbody>
              {schedule.rows.map((row) => (
                <tr key={row.month}>
                  <Td>{row.month}</Td>
                  <Td>{formatDate(`${row.due_date}T00:00:00Z`)}</Td>
                  <Td align="right">{formatAmount(row.payment, currency)}</Td>
                  <Td align="right" color={colors.danger}>
                    {formatAmount(row.interest, currency)}
                  </Td>
                  <Td align="right">{formatAmount(row.principal, currency)}</Td>
                  <Td align="right">
                    {formatAmount(row.remaining_balance, currency)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
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
        backgroundColor: colors.surfaceMuted,
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align = 'left',
  color,
}: {
  children: React.ReactNode;
  align?: 'left' | 'right';
  color?: string;
}) {
  return (
    <td
      style={{
        textAlign: align,
        padding: `${spacing.sm}px ${spacing.md}px`,
        borderBottom: `1px solid ${colors.border}`,
        color: color ?? colors.text,
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      {children}
    </td>
  );
}

function EmptyState({
  accountId,
  error,
}: {
  accountId: string;
  error: unknown;
}) {
  return (
    <Card
      style={{
        padding: spacing.xl,
        textAlign: 'center',
        border: `1px dashed ${colors.border}`,
        backgroundColor: colors.surfaceMuted,
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
        Faltan datos para calcular el cuadro
      </h2>
      <p
        style={{
          margin: `${spacing.sm}px 0`,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          maxWidth: 480,
          marginLeft: 'auto',
          marginRight: 'auto',
          lineHeight: 1.5,
        }}
      >
        Para generar el cuadro francés necesitamos el APR anual, el plazo
        en meses y la fecha de inicio del préstamo. Edita la cuenta y
        rellena los tres campos.
      </p>
      <Link
        href={`/settings/accounts`}
        style={{
          display: 'inline-block',
          padding: `${spacing.sm}px ${spacing.md}px`,
          backgroundColor: colors.primary,
          color: colors.onPrimary,
          borderRadius: radius.md,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          textDecoration: 'none',
        }}
      >
        Editar cuenta
      </Link>
      {error ? (
        <p
          style={{
            margin: `${spacing.md}px 0 0 0`,
            fontSize: fontSize.xs,
            color: colors.textSubtle,
          }}
        >
          {formatApiError(error, 'Detalle del backend')}
          {' · '}
          <span style={{ fontFamily: 'monospace' }}>{accountId}</span>
        </p>
      ) : null}
    </Card>
  );
}
