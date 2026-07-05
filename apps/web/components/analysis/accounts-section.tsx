'use client';

import { useAccountBalances } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { AccountBalance } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { AccountSwatch } from '@/components/accounts/account-swatch';
import { Card } from '@/components/ui/card';

function absBalance(a: AccountBalance): number {
  return Math.abs(Number(a.current_balance));
}

/**
 * PHASE-37.2 — Cuentas en una sección COLAPSABLE (`<details>` cerrado por
 * defecto), sustituyendo la grid siempre-visible del antiguo PositionHero.
 * Orden por |saldo| desc; las cuentas a 0 al final con opacidad reducida.
 */
export function AccountsSection() {
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;
  const balancesQuery = useAccountBalances(targetCurrency ? { targetCurrency } : {});
  const data = balancesQuery.data;
  const items = [...(data?.items ?? [])].sort((a, b) => absBalance(b) - absBalance(a));
  const currency = data?.reference_currency ?? storeCurrency;

  const debtCount = items.filter((a) => a.nature === 'liability').length;
  const unvaluedCount = items.filter((a) => a.is_unvalued).length;

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <details>
        <summary
          style={{
            listStyle: 'none',
            cursor: 'pointer',
            padding: `${spacing.md}px ${spacing.lg}px`,
            display: 'flex',
            alignItems: 'center',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            color: colors.text,
          }}
        >
          <span style={{ fontWeight: fontWeight.semibold }}>▸ {items.length} cuentas</span>
          <span style={{ color: colors.textMuted }}>
            · {debtCount} deuda · {unvaluedCount} no valorada
          </span>
          {data ? (
            <span
              style={{
                marginLeft: 'auto',
                fontWeight: fontWeight.semibold,
                fontVariantNumeric: 'tabular-nums',
                color: Number(data.net_worth) >= 0 ? colors.success : colors.danger,
              }}
            >
              patrimonio {formatAmount(data.net_worth, currency)}
            </span>
          ) : null}
        </summary>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: spacing.sm,
            padding: `0 ${spacing.lg}px ${spacing.lg}px`,
          }}
        >
          {items.map((a) => {
            const zero = absBalance(a) === 0;
            return (
              <div
                key={a.account_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing.sm,
                  padding: `${spacing.sm}px`,
                  borderRadius: radius.sm,
                  backgroundColor: colors.surfaceMuted,
                  opacity: zero ? 0.55 : 1,
                  minWidth: 0,
                }}
              >
                <AccountSwatch color={a.color} icon={a.icon} size={26} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: fontSize.sm,
                      fontWeight: fontWeight.medium,
                      color: colors.text,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    <span
                      style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {a.name}
                    </span>
                    {a.nature === 'liability' ? <Badge>DEUDA</Badge> : null}
                    {a.is_unvalued ? <Badge>NO VALORADA</Badge> : null}
                  </div>
                  <div
                    style={{
                      fontSize: fontSize.sm,
                      fontWeight: fontWeight.semibold,
                      color:
                        a.nature === 'liability'
                          ? colors.danger
                          : Number(a.current_balance) >= 0
                            ? colors.text
                            : colors.danger,
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {formatAmount(a.current_balance, a.currency)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </details>
    </Card>
  );
}

function Badge({ children }: { children: string }) {
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: fontWeight.semibold,
        letterSpacing: '0.04em',
        color: colors.textMuted,
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        padding: '1px 5px',
        borderRadius: 999,
        flexShrink: 0,
      }}
    >
      {children}
    </span>
  );
}
