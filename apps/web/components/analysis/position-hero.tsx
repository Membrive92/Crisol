'use client';

import { useMemo } from 'react';

import {
  useAccountBalances,
  useAccounts,
  useDebtHealth,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { AccountBalance, DtiStatus } from '@crisol/types';
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
import {
  AlertTriangleIcon,
  HeartPulseIcon,
  WalletIcon,
} from '@/components/ui/icons';

/**
 * PHASE-29.5 — `PositionHero` fusiona en una sola card las dos cards
 * de cabecera que vivían arriba de `/analysis`: `BalancesCard`
 * (patrimonio neto + composición) y `DebtHealthCard` (DTI + KPIs).
 *
 * Diseño en 3 secciones:
 * - ① Patrimonio neto: cifra grande + composition bar de cuentas
 *   activas (proporcionales a su magnitud absoluta).
 * - ② Salud de deuda: DTI con gauge + 4 KPIs (cuota, APR, intereses
 *   YTD, % en deuda).
 * - ③ Cuentas activas: grid 3 columnas con swatch + nombre + balance.
 *
 * Las cards legacy (`BalancesCard`, `DebtHealthCard`) se mantienen
 * intactas porque siguen siendo válidas en `/dashboard`, donde no se
 * sirve este hero más detallado.
 */
export function PositionHero() {
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
  // PHASE-30.6 — debt-health respeta el selector de divisa del header.
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;
  const balancesQuery = useAccountBalances();
  const accountsQuery = useAccounts({ includeArchived: true });
  const debtQuery = useDebtHealth(targetCurrency ? { targetCurrency } : {});

  const archivedIds = useMemo(() => {
    const set = new Set<string>();
    for (const account of accountsQuery.data ?? []) {
      if (account.is_archived) set.add(account.id);
    }
    return set;
  }, [accountsQuery.data]);

  if (balancesQuery.isLoading || debtQuery.isLoading) {
    return (
      <Card style={{ padding: spacing.lg }}>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando posición…
        </p>
      </Card>
    );
  }
  if (balancesQuery.isError || !balancesQuery.data) {
    return (
      <Card style={{ padding: spacing.lg }}>
        <p style={{ margin: 0, color: colors.danger, fontSize: fontSize.sm }}>
          Error cargando saldos por cuenta.
        </p>
      </Card>
    );
  }

  const balances = balancesQuery.data;
  const debt = debtQuery.data;
  const activeItems = balances.items.filter(
    (item) => !archivedIds.has(item.account_id),
  );
  const assetItems = activeItems.filter((item) => item.nature === 'asset');
  const liabilityItems = activeItems.filter((item) => item.nature === 'liability');
  const hasLiabilities = Number(balances.total_liabilities) > 0;
  const displayWorth = includeDebt ? balances.net_worth : balances.total_assets;
  const netWorthNegative = Number(displayWorth) < 0;
  const netWorthColor = netWorthNegative ? colors.danger : colors.text;

  return (
    <Card
      style={{
        padding: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          display: 'grid',
          // En desktop: net-worth | divider 1px | debt-health. En
          // pantallas <960px las dos secciones se apilan (declarado en
          // el `gridTemplateColumns` vía media query global más abajo).
          gridTemplateColumns: 'minmax(0, 1.05fr) 1px minmax(0, 1fr)',
        }}
        data-position-hero-grid="true"
      >
        <NetWorthSection
          displayWorth={displayWorth}
          netWorthColor={netWorthColor}
          referenceCurrency={balances.reference_currency}
          assetItems={assetItems}
          liabilityItems={liabilityItems}
          mixedCurrencies={balances.mixed_currencies}
          totalAssets={balances.total_assets}
          totalLiabilities={balances.total_liabilities}
          includeDebt={includeDebt}
          hasLiabilities={hasLiabilities}
        />
        <div
          aria-hidden
          style={{ width: 1, backgroundColor: colors.border }}
          data-position-hero-divider="true"
        />
        <DebtHealthSection debt={debt} />
      </div>

      <AccountsRow items={activeItems} />

      {/* Media query global: en <960px colapsa la columna del divider
          + apila las dos secciones; en <640px la grid de cuentas pasa
          de 3 a 1 columna. Sin Tailwind/NativeWind aquí, lo emitimos
          inline con un <style> local. */}
      <style>{`
        @media (max-width: 959px) {
          [data-position-hero-grid="true"] {
            grid-template-columns: 1fr !important;
          }
          [data-position-hero-divider="true"] {
            display: none !important;
          }
        }
        @media (max-width: 639px) {
          [data-position-hero-accounts="true"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </Card>
  );
}

/* -------- ① Patrimonio neto -------- */

function NetWorthSection({
  displayWorth,
  netWorthColor,
  referenceCurrency,
  assetItems,
  liabilityItems,
  mixedCurrencies,
  totalAssets,
  totalLiabilities,
  includeDebt,
  hasLiabilities,
}: {
  displayWorth: string;
  netWorthColor: string;
  referenceCurrency: string;
  assetItems: AccountBalance[];
  liabilityItems: AccountBalance[];
  mixedCurrencies: boolean;
  totalAssets: string;
  totalLiabilities: string;
  includeDebt: boolean;
  hasLiabilities: boolean;
}) {
  return (
    <section style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
        <IconBubble color={colors.primary} bg={colors.primarySoft}>
          <WalletIcon size={16} />
        </IconBubble>
        <Overline>
          Patrimonio neto
          {!includeDebt && hasLiabilities ? <SmallChip>Sin deuda</SmallChip> : null}
        </Overline>
      </header>

      <span
        style={{
          fontSize: fontSize.xxl,
          fontWeight: fontWeight.bold,
          color: netWorthColor,
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: '-0.02em',
          lineHeight: 1.1,
        }}
      >
        {formatAmount(displayWorth, referenceCurrency)}
      </span>

      {mixedCurrencies ? (
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
            Cuentas activas en monedas distintas — el total no convierte
            entre divisas.
          </span>
        </div>
      ) : null}

      <CompositionBar
        assetItems={assetItems}
        liabilityItems={liabilityItems}
        totalAssets={totalAssets}
        totalLiabilities={totalLiabilities}
        referenceCurrency={referenceCurrency}
        mixedCurrencies={mixedCurrencies}
      />
    </section>
  );
}

function CompositionBar({
  assetItems,
  liabilityItems,
  totalAssets,
  totalLiabilities,
  referenceCurrency,
  mixedCurrencies,
}: {
  assetItems: AccountBalance[];
  liabilityItems: AccountBalance[];
  totalAssets: string;
  totalLiabilities: string;
  referenceCurrency: string;
  mixedCurrencies: boolean;
}) {
  // Con divisas mixtas, sumar magnitudes de cuentas sin convertir produce
  // pesos sin sentido (un saldo de 1.000 ¥ y otro de 1.000 € no son
  // comparables). El banner de aviso ya está arriba; aquí no pintamos la
  // barra para no comunicar una composición falsa. No inventamos
  // conversión client-side.
  if (mixedCurrencies) {
    return (
      <div
        style={{
          fontSize: fontSize.xs,
          color: colors.textSubtle,
          padding: `${spacing.sm}px 0`,
        }}
      >
        Composición no disponible con cuentas en varias divisas.
      </div>
    );
  }
  const totalAssetsNum = Math.max(0, Number(totalAssets));
  const totalLiabsNum = Math.max(0, Number(totalLiabilities));
  const grandTotal = totalAssetsNum + totalLiabsNum;
  if (grandTotal === 0) {
    return (
      <div
        style={{
          fontSize: fontSize.xs,
          color: colors.textSubtle,
          padding: `${spacing.sm}px 0`,
        }}
      >
        Sin actividad en este momento.
      </div>
    );
  }
  const leftFlex = totalAssetsNum / grandTotal;
  const rightFlex = totalLiabsNum / grandTotal;
  return (
    <div>
      <div
        role="img"
        aria-label="Composición: activos vs pasivos"
        style={{
          display: 'grid',
          gridTemplateColumns: `${leftFlex}fr ${rightFlex}fr`,
          height: 14,
          borderRadius: 7,
          overflow: 'hidden',
          backgroundColor: colors.surfaceMuted,
        }}
      >
        <div style={{ display: 'flex' }}>
          {assetItems.map((item, idx) => {
            const value = Math.abs(Number(item.current_balance));
            return (
              <span
                key={item.account_id}
                title={`${item.name} · ${formatAmount(
                  item.current_balance,
                  item.currency,
                )}`}
                style={{
                  flex: value,
                  backgroundColor: item.color ?? colors.primary,
                  borderRight:
                    idx < assetItems.length - 1
                      ? `2px solid ${colors.surface}`
                      : 'none',
                }}
              />
            );
          })}
        </div>
        <div style={{ display: 'flex' }}>
          {liabilityItems.map((item, idx) => {
            const value = Math.abs(Number(item.current_balance));
            return (
              <span
                key={item.account_id}
                title={`${item.name} · ${formatAmount(
                  item.current_balance,
                  item.currency,
                )}`}
                style={{
                  flex: value,
                  backgroundColor: item.color ?? colors.danger,
                  opacity: 0.92,
                  borderLeft:
                    idx > 0 ? `2px solid ${colors.surface}` : 'none',
                }}
              />
            );
          })}
        </div>
      </div>
      <div
        style={{
          marginTop: spacing.xs,
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: fontSize.xs,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span style={{ color: colors.income, fontWeight: fontWeight.semibold }}>
          +{formatAmount(totalAssets, referenceCurrency)}
        </span>
        {totalLiabsNum > 0 ? (
          <span
            style={{
              color: colors.danger,
              fontWeight: fontWeight.semibold,
            }}
          >
            −{formatAmount(totalLiabilities, referenceCurrency)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/* -------- ② Salud de deuda -------- */

function DebtHealthSection({ debt }: { debt: ReturnType<typeof useDebtHealth>['data'] }) {
  if (!debt) {
    return (
      <section style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando indicadores de deuda…
        </p>
      </section>
    );
  }
  const hasDebt = Number(debt.total_liabilities) > 0;
  if (!hasDebt) {
    return (
      <section
        style={{
          padding: spacing.lg,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}
      >
        <header style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
          <IconBubble color={colors.success} bg={colors.successSoft}>
            <HeartPulseIcon size={16} />
          </IconBubble>
          <Overline>Salud de deuda</Overline>
        </header>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.5 }}>
          Sin deudas registradas. Cuando añadas una tarjeta, préstamo o
          hipoteca verás aquí ratios de salud financiera.
        </p>
      </section>
    );
  }

  const dtiTone = dtiStatusColors(debt.dti_status);
  const dtiPct = debt.dti_ratio !== null ? debt.dti_ratio * 100 : null;
  const dtiWidth = Math.max(2, Math.min(100, dtiPct ?? 0));
  const aprPct = debt.weighted_apr !== null ? (debt.weighted_apr * 100).toFixed(2) : null;
  const debtToAssetsPct =
    debt.debt_to_assets_ratio !== null
      ? (debt.debt_to_assets_ratio * 100).toFixed(1)
      : null;

  return (
    <section
      style={{
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
        }}
      >
        <IconBubble color={dtiTone.fg} bg={dtiTone.bg}>
          <HeartPulseIcon size={16} />
        </IconBubble>
        <Overline>Salud de deuda</Overline>
        <span
          style={{
            marginLeft: 'auto',
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 8px',
            borderRadius: 999,
            backgroundColor: dtiTone.bg,
            color: dtiTone.fg,
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          Esfuerzo · {dtiTone.label}
        </span>
      </header>

      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: spacing.sm,
        }}
      >
        <span
          style={{
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          {dtiPct !== null ? `${dtiPct.toFixed(1)} %` : '—'}
        </span>
        <span style={{ fontSize: fontSize.xs, color: colors.textSubtle, textAlign: 'right' }}>
          tasa de esfuerzo (BdE)
          <br />
          umbral 35 %
        </span>
      </div>

      <DtiGauge widthPct={dtiWidth} status={debt.dti_status} />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: spacing.md,
          borderTop: `1px solid ${colors.border}`,
          paddingTop: spacing.md,
        }}
      >
        <Kpi
          label="Cuota mensual"
          value={formatAmount(debt.monthly_debt_payment, debt.reference_currency)}
        />
        <Kpi label="APR medio" value={aprPct !== null ? `${aprPct} %` : '—'} />
        <Kpi
          label="Intereses YTD"
          value={formatAmount(debt.interest_paid_ytd, debt.reference_currency)}
          valueColor={colors.danger}
        />
        <Kpi
          label="% en deuda"
          value={debtToAssetsPct !== null ? `${debtToAssetsPct} %` : '—'}
        />
      </div>
    </section>
  );
}

function DtiGauge({ widthPct, status }: { widthPct: number; status: DtiStatus }) {
  const fillColor =
    status === 'stressed'
      ? colors.danger
      : status === 'caution'
        ? colors.warning
        : colors.success;
  return (
    <div>
      <div
        style={{
          position: 'relative',
          height: 6,
          borderRadius: 3,
          backgroundColor: colors.surfaceMuted,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${widthPct}%`,
            height: '100%',
            backgroundColor: fillColor,
            transition: 'width 200ms ease',
          }}
        />
        {/* Threshold markers a 35% (warning) y 60% (danger). */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: '35%',
            top: 0,
            bottom: 0,
            width: 1,
            backgroundColor: colors.warning,
          }}
        />
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: '60%',
            top: 0,
            bottom: 0,
            width: 1,
            backgroundColor: colors.danger,
          }}
        />
      </div>
      <div
        style={{
          marginTop: 4,
          display: 'grid',
          gridTemplateColumns: 'auto auto auto auto',
          justifyContent: 'space-between',
          fontSize: 10,
          color: colors.textSubtle,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        <span>0 %</span>
        <span>35 %</span>
        <span>60 %</span>
        <span>100 %</span>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: fontWeight.semibold,
          color: colors.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: valueColor ?? colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
      </span>
    </div>
  );
}

/* -------- ③ Cuentas activas -------- */

function AccountsRow({ items }: { items: AccountBalance[] }) {
  if (items.length === 0) return null;
  return (
    <section
      style={{
        borderTop: `1px solid ${colors.border}`,
        padding: '18px 24px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <Overline>Cuentas activas · {items.length}</Overline>
      <div
        data-position-hero-accounts="true"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
          gap: spacing.md,
        }}
      >
        {items.map((item) => (
          <AccountTile key={item.account_id} item={item} />
        ))}
      </div>
    </section>
  );
}

function AccountTile({ item }: { item: AccountBalance }) {
  const isLiability = item.nature === 'liability';
  const amountColor = isLiability ? colors.danger : colors.text;
  const amountPrefix = isLiability ? '-' : '';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        minWidth: 0,
      }}
    >
      <AccountSwatch color={item.color} icon={item.icon} size={28} />
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          lineHeight: 1.2,
        }}
      >
        <span
          style={{
            fontSize: 13,
            fontWeight: fontWeight.medium,
            color: colors.text,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {item.name}
          {isLiability ? (
            <span
              style={{
                marginLeft: 6,
                fontSize: 9.5,
                fontWeight: fontWeight.semibold,
                color: colors.danger,
                backgroundColor: colors.dangerSoft,
                padding: '1px 5px',
                borderRadius: 4,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              Deuda
            </span>
          ) : null}
          {item.is_unvalued ? (
            <span
              title="Esta cuenta no entra al cálculo de patrimonio neto. Cuando exista el módulo de inversión real, se reincorporará con su valoración de mercado."
              style={{
                marginLeft: 6,
                fontSize: 9.5,
                fontWeight: fontWeight.semibold,
                color: colors.textMuted,
                backgroundColor: colors.surfaceMuted,
                padding: '1px 5px',
                borderRadius: 4,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              No valorada
            </span>
          ) : null}
        </span>
        <span
          style={{
            fontSize: 13,
            fontWeight: fontWeight.semibold,
            color: amountColor,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {amountPrefix}
          {formatAmount(item.current_balance, item.currency)}
        </span>
      </div>
    </div>
  );
}

/* -------- helpers visuales -------- */

function IconBubble({
  children,
  color,
  bg,
}: {
  children: React.ReactNode;
  color: string;
  bg: string;
}) {
  return (
    <span
      aria-hidden
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        backgroundColor: bg,
        color,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: '0 0 auto',
      }}
    >
      {children}
    </span>
  );
}

function Overline({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: spacing.xs,
        fontSize: 11,
        fontWeight: fontWeight.semibold,
        color: colors.textMuted,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
      }}
    >
      {children}
    </span>
  );
}

function SmallChip({ children }: { children: React.ReactNode }) {
  return (
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
      {children}
    </span>
  );
}

function dtiStatusColors(status: DtiStatus): { bg: string; fg: string; label: string } {
  switch (status) {
    case 'healthy':
      return { bg: colors.successSoft, fg: colors.success, label: 'Saludable' };
    case 'caution':
      return { bg: colors.warningSoft, fg: colors.warning, label: 'Atención' };
    case 'stressed':
      return { bg: colors.dangerSoft, fg: colors.danger, label: 'Estresado' };
    case 'unknown':
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted, label: 'Sin datos' };
  }
}
