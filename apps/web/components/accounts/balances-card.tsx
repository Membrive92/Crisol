'use client';

import { useMemo, useState } from 'react';

import { useAccountBalances, useAccounts } from '@finanzas/services';
import type { AccountBalance } from '@finanzas/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@finanzas/ui';

import { AccountSwatch } from '@/components/accounts/account-swatch';
import { Card } from '@/components/ui/card';
import { AlertTriangleIcon, WalletIcon } from '@/components/ui/icons';

export interface BalancesCardProps {
  /**
   * Variante visual:
   * - `full` (por defecto) — muestra el desglose completo de cuentas
   *   activas siempre visible.
   * - `compact` — sólo muestra la cabecera + totales; el desglose se
   *   despliega al pulsar "Ver desglose". Pensado para mobile o para
   *   meterse en bentos pequeños sin abrumar.
   */
  variant?: 'full' | 'compact';
}

/**
 * Card de saldo agregado por cuenta (PHASE-19.4).
 *
 * Muestra el patrimonio neto en `reference_currency` (suma cruda de
 * cuentas activas; los archivados están en `items` pero el backend ya
 * los excluye de los totales). Si `mixed_currencies` es true se pinta
 * un warning sutil porque los totales no convierten entre divisas.
 */
export function BalancesCard({ variant = 'full' }: BalancesCardProps) {
  const { data, isLoading, isError } = useAccountBalances();
  // El payload de balances incluye archivadas en `items` (display
  // sólo) pero la spec pide ocultarlas en el desglose. Necesitamos
  // el flag `is_archived` que vive en `Account`, así que cruzamos.
  const { data: accounts } = useAccounts({ includeArchived: true });
  // En `compact` el desglose arranca colapsado; en `full` siempre
  // visible. El estado sólo se usa cuando estamos en `compact`.
  const [expanded, setExpanded] = useState(false);

  const archivedIds = useMemo(() => {
    const set = new Set<string>();
    for (const account of accounts ?? []) {
      if (account.is_archived) set.add(account.id);
    }
    return set;
  }, [accounts]);

  if (isLoading) {
    return (
      <Card style={{ padding: spacing.md }}>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando saldos…
        </p>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card style={{ padding: spacing.md }}>
        <p style={{ margin: 0, color: colors.danger, fontSize: fontSize.sm }}>
          Error cargando saldos por cuenta.
        </p>
      </Card>
    );
  }

  // El backend ya excluye archivadas del cómputo de totales, pero
  // viene en `items` para uso del consumidor (ej. settings/accounts
  // las muestra). Aquí queremos sólo activas.
  const activeItems = data.items.filter((item) => !archivedIds.has(item.account_id));
  const showDetail = variant === 'full' || expanded;

  return (
    <Card
      style={{
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
        }}
      >
        <div
          aria-hidden
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            backgroundColor: colors.primarySoft,
            color: colors.primary,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            flex: '0 0 auto',
          }}
        >
          <WalletIcon size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              color: colors.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              display: 'block',
            }}
          >
            Patrimonio neto
          </span>
          <span
            style={{
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '-0.01em',
              lineHeight: 1.1,
            }}
          >
            {formatAmount(data.net_worth, data.reference_currency)}
          </span>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: spacing.md,
          fontSize: fontSize.sm,
        }}
      >
        <SubtotalRow
          label="Activos"
          value={formatAmount(data.total_assets, data.reference_currency)}
          color={colors.income}
        />
        <SubtotalRow
          label="Pasivos"
          value={formatAmount(data.total_liabilities, data.reference_currency)}
          color={colors.textMuted}
        />
      </div>

      {data.mixed_currencies ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: spacing.xs,
            backgroundColor: colors.warningSoft,
            color: colors.warning,
            padding: `${spacing.xs}px ${spacing.sm}px`,
            borderRadius: radius.sm,
            fontSize: fontSize.xs,
            lineHeight: 1.4,
          }}
        >
          <span style={{ flex: '0 0 auto', marginTop: 2 }}>
            <AlertTriangleIcon size={14} />
          </span>
          <span>
            Las cuentas activas tienen monedas distintas — el total no
            convierte entre divisas.
          </span>
        </div>
      ) : null}

      {variant === 'compact' && activeItems.length > 0 ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            color: colors.textMuted,
            fontSize: fontSize.xs,
            fontWeight: fontWeight.medium,
            textAlign: 'left',
          }}
        >
          {expanded ? '▾ Ocultar desglose' : `▸ Ver desglose (${activeItems.length})`}
        </button>
      ) : null}

      {showDetail ? (
        <ul
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.xs,
            borderTop: `1px solid ${colors.border}`,
            paddingTop: spacing.sm,
          }}
        >
          {activeItems.length === 0 ? (
            <li
              style={{ fontSize: fontSize.xs, color: colors.textMuted }}
            >
              No hay cuentas activas.
            </li>
          ) : (
            activeItems.map((item) => (
              <BalanceRow key={item.account_id} item={item} />
            ))
          )}
        </ul>
      ) : null}
    </Card>
  );
}

function SubtotalRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4 }}>
      <span
        style={{
          fontSize: fontSize.xs,
          color: colors.textMuted,
          fontWeight: fontWeight.medium,
        }}
      >
        {label}:
      </span>
      <span
        style={{
          fontWeight: fontWeight.semibold,
          color,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </span>
    </span>
  );
}

function BalanceRow({ item }: { item: AccountBalance }) {
  const isLiability = item.nature === 'liability';
  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
      }}
    >
      <AccountSwatch color={item.color} icon={item.icon} size={24} />
      <span
        style={{
          flex: 1,
          minWidth: 0,
          fontSize: fontSize.sm,
          color: colors.text,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {item.name}
      </span>
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: isLiability ? colors.expense : colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatAmount(item.current_balance, item.currency)}
      </span>
    </li>
  );
}

