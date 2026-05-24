'use client';

import Link from 'next/link';
import { useState } from 'react';

import { useAccounts } from '@crisol/services';
import type { Account, AccountBalance, AccountType } from '@crisol/types';
import { AMORTIZABLE_ACCOUNT_TYPES } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountSwatch } from '@/components/accounts/account-swatch';
import { DebtPaymentWizard } from '@/components/accounts/debt-payment-wizard';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

const TYPE_LABEL: Record<AccountType, string> = {
  bank: 'Banco',
  savings: 'Ahorro',
  brokerage: 'Bróker',
  crypto: 'Crypto',
  cash: 'Efectivo',
  credit_card: 'Tarjeta de crédito',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

export interface DebtListProps {
  liabilities: AccountBalance[];
  loading: boolean;
}

/**
 * Calcula la cuota mensual francesa para un préstamo con APR anual.
 *
 * `cuota = P × (i × (1+i)^n) / ((1+i)^n - 1)` donde `i = apr/12` y `n
 * = term_months`. Si `apr` es 0 devolvemos `P/n` (préstamo sin
 * intereses). Devuelve `null` cuando falta cualquier dato.
 */
function estimateMonthlyPayment(account: Account): number | null {
  if (!AMORTIZABLE_ACCOUNT_TYPES.includes(account.type)) return null;
  const apr = account.apr ? Number(account.apr) : null;
  const term = account.term_months;
  const principal = Number(account.opening_balance);
  if (
    apr === null ||
    !Number.isFinite(apr) ||
    !term ||
    !Number.isFinite(principal) ||
    principal <= 0
  ) {
    return null;
  }
  if (apr === 0) {
    return principal / term;
  }
  const i = apr / 12;
  const factor = Math.pow(1 + i, term);
  const cuota = (principal * (i * factor)) / (factor - 1);
  return Number.isFinite(cuota) ? cuota : null;
}

/**
 * Lista de pasivos con KPIs por fila (PHASE-22+). Cada fila resume:
 *
 * - Icono + nombre + tipo legible de la cuenta.
 * - Saldo pendiente (positivo decimal) en color danger.
 * - APR anual si aplica (loan/mortgage).
 * - Cuota mensual estimada según el cuadro francés cuando los tres
 *   inputs están presentes (`apr`, `term_months`, `opening_balance`).
 * - Acciones: "Pagar cuota" (abre `DebtPaymentWizard`) y "Ver cuadro"
 *   (link al cuadro francés en `/accounts/{id}/amortization`, sólo
 *   para tipos amortizables).
 *
 * Si el usuario no tiene pasivos pintamos una empty card con CTA a
 * settings/accounts.
 */
export function DebtList({ liabilities, loading }: DebtListProps) {
  // Necesitamos `apr/term_months/start_date` que viven en `Account`
  // pero no en `AccountBalance`. Cruzamos por id; incluimos
  // archivadas porque ayudan a renderizar el nombre/color aunque, en
  // la práctica, balances ya filtra archivadas.
  const accountsQuery = useAccounts({ includeArchived: true });
  const accounts = accountsQuery.data ?? [];

  if (loading) {
    return (
      <Card style={{ padding: spacing.md }}>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando deudas…
        </p>
      </Card>
    );
  }

  if (liabilities.length === 0) {
    return (
      <Card
        style={{
          padding: spacing.xl,
          textAlign: 'center',
          backgroundColor: colors.surfaceMuted,
          border: `1px dashed ${colors.border}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: spacing.md,
        }}
      >
        <div>
          <h3
            style={{
              margin: 0,
              fontSize: fontSize.lg,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Aún no tienes deuda registrada
          </h3>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              maxWidth: 480,
              lineHeight: 1.5,
            }}
          >
            Cuando añadas una tarjeta de crédito, préstamo o hipoteca verás
            aquí el detalle de cada pasivo con sus cuotas estimadas y enlaces
            al cuadro de amortización.
          </p>
        </div>
        <Link
          href="/settings/accounts"
          style={{
            display: 'inline-block',
            padding: `${spacing.sm}px ${spacing.md}px`,
            borderRadius: radius.md,
            backgroundColor: colors.primary,
            color: colors.onPrimary,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            textDecoration: 'none',
          }}
        >
          Añadir deuda
        </Link>
      </Card>
    );
  }

  return (
    <Card
      style={{
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <header style={{ marginBottom: spacing.xs }}>
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Tus deudas
        </h2>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.xs,
            color: colors.textMuted,
          }}
        >
          {liabilities.length}{' '}
          {liabilities.length === 1 ? 'pasivo activo' : 'pasivos activos'}
        </p>
      </header>

      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.sm,
        }}
      >
        {liabilities.map((item) => {
          const account = accounts.find((a) => a.id === item.account_id);
          return (
            <DebtRow
              key={item.account_id}
              balance={item}
              {...(account ? { account } : {})}
            />
          );
        })}
      </ul>
    </Card>
  );
}

interface DebtRowProps {
  balance: AccountBalance;
  account?: Account;
}

function DebtRow({ balance, account }: DebtRowProps) {
  const [payingDebt, setPayingDebt] = useState(false);

  const isAmortizable =
    AMORTIZABLE_ACCOUNT_TYPES.includes(balance.type);
  const monthlyPayment = account ? estimateMonthlyPayment(account) : null;
  const aprValue = account?.apr ?? null;
  const aprPercent =
    aprValue !== null ? (Number(aprValue) * 100).toFixed(2) : null;
  const typeLabel = TYPE_LABEL[balance.type] ?? balance.type;

  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        flexWrap: 'wrap',
      }}
    >
      <AccountSwatch color={balance.color} icon={balance.icon} size={36} />

      <div style={{ flex: 1, minWidth: 160 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing.xs,
            flexWrap: 'wrap',
          }}
        >
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            {balance.name}
          </span>
          <span
            style={{
              fontSize: 10,
              fontWeight: fontWeight.semibold,
              color: colors.textMuted,
              backgroundColor: colors.surface,
              padding: '1px 6px',
              borderRadius: radius.sm,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              border: `1px solid ${colors.border}`,
            }}
          >
            {typeLabel}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: spacing.md,
            flexWrap: 'wrap',
            marginTop: 2,
            fontSize: fontSize.xs,
            color: colors.textMuted,
          }}
        >
          {aprPercent !== null ? <span>{aprPercent}% APR</span> : null}
          {monthlyPayment !== null ? (
            <span>
              Cuota est.{' '}
              <span
                style={{
                  color: colors.text,
                  fontWeight: fontWeight.medium,
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {formatAmount(
                  String(monthlyPayment.toFixed(2)),
                  balance.currency,
                )}
              </span>
            </span>
          ) : null}
          {account?.term_months ? (
            <span>{account.term_months} cuotas totales</span>
          ) : null}
        </div>
      </div>

      <div
        style={{
          textAlign: 'right',
          fontSize: fontSize.lg,
          fontWeight: fontWeight.bold,
          color: colors.danger,
          fontVariantNumeric: 'tabular-nums',
          minWidth: 120,
        }}
      >
        {formatAmount(balance.current_balance, balance.currency)}
      </div>

      <div
        style={{
          display: 'flex',
          gap: spacing.xs,
          flexWrap: 'wrap',
          justifyContent: 'flex-end',
        }}
      >
        {account ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => setPayingDebt(true)}
          >
            Pagar cuota
          </Button>
        ) : null}
        {isAmortizable ? (
          <Link
            href={`/personal-finance/accounts/${balance.account_id}/amortization`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: `${spacing.sm}px ${spacing.md}px`,
              borderRadius: radius.md,
              border: `1px solid ${colors.border}`,
              color: colors.text,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              textDecoration: 'none',
              backgroundColor: 'transparent',
            }}
          >
            Ver cuadro
          </Link>
        ) : null}
      </div>

      {account && payingDebt ? (
        <DebtPaymentWizard
          liabilityAccount={account}
          open={payingDebt}
          onClose={() => setPayingDebt(false)}
        />
      ) : null}
    </li>
  );
}
