'use client';

import { useMemo, useState } from 'react';

import { useAccountBalances, useAccounts } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { AccountBalance } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

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
 * Card de saldo agregado por cuenta (PHASE-19.4, ampliada en PHASE-22).
 *
 * Muestra el patrimonio neto en `reference_currency` calculado como
 * `total_assets - total_liabilities` (los pasivos llegan con magnitud
 * positiva del backend y ya se restaron para `net_worth`). Cuando el
 * patrimonio neto es negativo, el valor se pinta en color danger.
 *
 * Las liabilities se renderizan en su propia sección visual y cada fila
 * pinta su `current_balance` en color expense con un badge "DEUDA".
 */
export function BalancesCard({ variant = 'full' }: BalancesCardProps) {
  const { data, isLoading, isError } = useAccountBalances();
  // El payload de balances incluye archivadas en `items` (display
  // sólo) pero la spec pide ocultarlas en el desglose. Necesitamos
  // el flag `is_archived` que vive en `Account`, así que cruzamos.
  const { data: accounts } = useAccounts({ includeArchived: true });
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
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
      <Card>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando saldos…
        </p>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
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

  const assetItems = activeItems.filter((item) => item.nature === 'asset');
  const liabilityItems = activeItems.filter((item) => item.nature === 'liability');

  const hasLiabilities = Number(data.total_liabilities) > 0;
  // Cuando `includeDebt` está OFF la cifra grande muestra sólo activos.
  // El desglose de pasivos se mantiene visible para no esconder
  // información — el toggle sólo afecta al agregado.
  const displayWorth = includeDebt ? data.net_worth : data.total_assets;
  const netWorthNegative = Number(displayWorth) < 0;
  const netWorthColor = netWorthNegative ? colors.danger : colors.text;

  return (
    <Card
      style={{
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
              display: 'inline-flex',
              alignItems: 'center',
              gap: spacing.xs,
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              color: colors.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Patrimonio neto
            {!includeDebt && hasLiabilities ? (
              <span
                style={{
                  fontSize: 10,
                  color: colors.textMuted,
                  backgroundColor: colors.surfaceMuted,
                  padding: '1px 6px',
                  borderRadius: radius.sm,
                  letterSpacing: '0.04em',
                }}
              >
                Sin deuda
              </span>
            ) : null}
          </span>
          <span
            style={{
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: netWorthColor,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '-0.01em',
              lineHeight: 1.1,
              display: 'block',
            }}
          >
            {formatAmount(displayWorth, data.reference_currency)}
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
        {hasLiabilities ? (
          <SubtotalRow
            label="Pasivos"
            value={`-${formatAmount(data.total_liabilities, data.reference_currency)}`}
            color={colors.danger}
          />
        ) : null}
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
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.sm,
            borderTop: `1px solid ${colors.border}`,
            paddingTop: spacing.sm,
          }}
        >
          {activeItems.length === 0 ? (
            <p style={{ margin: 0, fontSize: fontSize.xs, color: colors.textMuted }}>
              No hay cuentas activas.
            </p>
          ) : (
            <>
              {assetItems.length > 0 ? (
                <BalanceGroup title="Activos" items={assetItems} />
              ) : null}
              {liabilityItems.length > 0 ? (
                <BalanceGroup title="Pasivos" items={liabilityItems} />
              ) : null}
            </>
          )}
        </div>
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

function BalanceGroup({
  title,
  items,
}: {
  title: string;
  items: AccountBalance[];
}) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      <h4
        style={{
          margin: 0,
          fontSize: 11,
          fontWeight: fontWeight.semibold,
          color: colors.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {title}
      </h4>
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.xs,
        }}
      >
        {items.map((item) => (
          <BalanceRow key={item.account_id} item={item} />
        ))}
      </ul>
    </section>
  );
}

function BalanceRow({ item }: { item: AccountBalance }) {
  const isLiability = item.nature === 'liability';
  const amountColor = isLiability ? colors.danger : colors.text;
  const amountPrefix = isLiability ? '-' : '';
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
          display: 'inline-flex',
          alignItems: 'center',
          gap: spacing.xs,
        }}
      >
        {item.name}
        {isLiability ? (
          <span
            style={{
              fontSize: 10,
              fontWeight: fontWeight.semibold,
              color: colors.danger,
              backgroundColor: colors.dangerSoft,
              padding: '1px 6px',
              borderRadius: radius.sm,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              flex: '0 0 auto',
            }}
          >
            Deuda
          </span>
        ) : null}
      </span>
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: amountColor,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {amountPrefix}
        {formatAmount(item.current_balance, item.currency)}
      </span>
    </li>
  );
}
