'use client';

import Link from 'next/link';
import { Fragment, useState } from 'react';

import { useAccounts, useCategories } from '@crisol/services';
import type { Account, AccountBalance, AccountType, Category } from '@crisol/types';
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
 * PHASE-35 — Total de deuda de una tarjeta incluyendo sus compras a plazos.
 * Suma el saldo de la tarjeta padre con el de cada hija. En céntimos para
 * evitar el artefacto de float al sumar strings decimales.
 *
 * AUDIT-2026-06 — Devuelve `null` si alguna hija está en OTRA divisa: no se
 * pueden sumar divisas distintas sin convertir, y antes se descartaban en
 * silencio (el total combinado quedaba incompleto sin avisar). Con
 * `convertAll` el backend ya homogeneiza todas las cuentas al target, así
 * que esto sólo salta en modo nativo con una compra a plazos en divisa
 * distinta a su tarjeta (anómalo). En ese caso el caller no pinta el total
 * combinado; cada hija sigue visible en su propia fila con su saldo.
 */
function groupTotalForCard(
  parent: AccountBalance,
  children: readonly AccountBalance[],
): string | null {
  if (children.some((child) => child.currency !== parent.currency)) {
    return null;
  }
  let cents = Math.round(Number(parent.current_balance) * 100);
  for (const child of children) {
    cents += Math.round(Number(child.current_balance) * 100);
  }
  return (cents / 100).toFixed(2);
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
  const categoriesQuery = useCategories();
  const categoriesById = new Map<string, Category>(
    (categoriesQuery.data ?? []).map((c) => [c.id, c]),
  );

  // PHASE-35 — agrupar las compras a plazos (hijas) bajo su tarjeta padre.
  // Las hijas salen de la lista de nivel superior y se anidan bajo el padre.
  // Una hija cuyo padre no esté presente (p. ej. archivado) cae a nivel
  // superior para no perderse.
  const childrenByParent = new Map<string, AccountBalance[]>();
  for (const item of liabilities) {
    if (item.parent_account_id) {
      const siblings = childrenByParent.get(item.parent_account_id) ?? [];
      siblings.push(item);
      childrenByParent.set(item.parent_account_id, siblings);
    }
  }
  const topLevelIds = new Set(
    liabilities.filter((i) => !i.parent_account_id).map((i) => i.account_id),
  );
  const topLevel = liabilities.filter(
    (i) => !i.parent_account_id || !topLevelIds.has(i.parent_account_id),
  );

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
        {topLevel.map((item) => {
          const account = accounts.find((a) => a.id === item.account_id);
          const category =
            account?.category_id != null
              ? categoriesById.get(account.category_id) ?? null
              : null;
          const children = childrenByParent.get(item.account_id) ?? [];
          const combinedTotal =
            children.length > 0 ? groupTotalForCard(item, children) : null;
          const groupTotal =
            combinedTotal !== null
              ? {
                  total: combinedTotal,
                  currency: item.currency,
                  count: children.length,
                }
              : undefined;
          return (
            <Fragment key={item.account_id}>
              <DebtRow
                balance={item}
                {...(account ? { account } : {})}
                {...(category ? { category } : {})}
                {...(groupTotal ? { groupTotal } : {})}
              />
              {children.map((child) => {
                const childAccount = accounts.find((a) => a.id === child.account_id);
                const childCategory =
                  childAccount?.category_id != null
                    ? categoriesById.get(childAccount.category_id) ?? null
                    : null;
                return (
                  <DebtRow
                    key={child.account_id}
                    balance={child}
                    isChild
                    {...(childAccount ? { account: childAccount } : {})}
                    {...(childCategory ? { category: childCategory } : {})}
                  />
                );
              })}
            </Fragment>
          );
        })}
      </ul>
    </Card>
  );
}

interface DebtRowProps {
  balance: AccountBalance;
  account?: Account;
  category?: Category;
  /** PHASE-35 — fila anidada: compra a plazos bajo una tarjeta padre. */
  isChild?: boolean;
  /** PHASE-35 — en una tarjeta CON compras a plazos, su total combinado
   * (tarjeta + hijas de su misma moneda) y cuántas compras agrupa. */
  groupTotal?: { total: string; currency: string; count: number } | undefined;
}

function DebtRow({ balance, account, category, isChild = false, groupTotal }: DebtRowProps) {
  const [payingDebt, setPayingDebt] = useState(false);

  const isAmortizable =
    AMORTIZABLE_ACCOUNT_TYPES.includes(balance.type);
  const monthlyPayment = account ? estimateMonthlyPayment(account) : null;
  const aprValue = account?.apr ?? null;
  const aprPercent =
    aprValue !== null ? (Number(aprValue) * 100).toFixed(2) : null;
  // PHASE-35: una hija es una "compra a plazos"; su tipo real (credit_card)
  // confundiría, así que se etiqueta como tal.
  const typeLabel = isChild ? 'Compra a plazos' : TYPE_LABEL[balance.type] ?? balance.type;

  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: isChild ? colors.surface : colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderLeft: isChild ? `3px solid ${colors.primary}` : `1px solid ${colors.border}`,
        borderRadius: radius.md,
        flexWrap: 'wrap',
        ...(isChild ? { marginLeft: spacing.lg } : {}),
      }}
    >
      <AccountSwatch color={balance.color} icon={balance.icon} size={isChild ? 28 : 36} />

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
          {category ? (
            <span
              title={`Categoría vinculada: ${category.name}`}
              style={{
                fontSize: 10,
                fontWeight: fontWeight.semibold,
                color: colors.primary,
                backgroundColor: 'transparent',
                padding: '1px 6px',
                borderRadius: radius.sm,
                letterSpacing: '0.04em',
                border: `1px solid ${colors.primary}`,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
              }}
            >
              {category.icon ? <span aria-hidden>{category.icon}</span> : null}
              <span>{category.name}</span>
            </span>
          ) : null}
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
          {groupTotal ? (
            <span>
              {groupTotal.count}{' '}
              {groupTotal.count === 1 ? 'compra a plazos' : 'compras a plazos'}
            </span>
          ) : null}
        </div>
      </div>

      <div style={{ textAlign: 'right', minWidth: 120 }}>
        <div
          style={{
            fontSize: fontSize.lg,
            fontWeight: fontWeight.bold,
            color: colors.danger,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {formatAmount(balance.current_balance, balance.currency)}
        </div>
        {groupTotal ? (
          // PHASE-35: total de la tarjeta incluyendo sus compras a plazos.
          <div
            style={{
              marginTop: 2,
              fontSize: fontSize.xs,
              color: colors.textMuted,
            }}
          >
            Con plazos:{' '}
            <strong style={{ color: colors.text, fontVariantNumeric: 'tabular-nums' }}>
              {formatAmount(groupTotal.total, groupTotal.currency)}
            </strong>
          </div>
        ) : null}
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
