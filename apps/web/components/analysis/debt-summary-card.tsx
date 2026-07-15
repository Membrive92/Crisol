'use client';

import { useMemo, useState } from 'react';

import {
  useAccountBalances,
  useCategories,
  useDebtHealth,
  useTransactions,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { AccountNature, CategoryRole, DtiStatus, Transaction } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card, CardTitle } from '@/components/ui/card';
import { HeartPulseIcon, TrendingDownIcon, TrendingUpIcon } from '@/components/ui/icons';

/**
 * Separa una descripción bancaria en su parte legible y los últimos 4 dígitos
 * de la referencia numérica final (nº de cuenta/tarjeta), para de-enfatizar el
 * número largo: `"Cargo por amortizacion … 0182-1051-19-0830170370"` →
 * `{ main: "Cargo por amortizacion …", ref4: "0370" }`. Si no hay número final
 * reconocible, `ref4` es `null` y `main` es la descripción completa.
 */
export function splitDebtLabel(description: string): { main: string; ref4: string | null } {
  const m = description.match(/^(.*?)[\s:]*(\d[\d\-/ ]{4,}\d)\s*$/);
  const main = m?.[1]?.trim();
  if (!m || !main) return { main: description.trim(), ref4: null };
  const digits = (m[2] ?? '').replace(/\D/g, '');
  return { main, ref4: digits.length >= 4 ? digits.slice(-4) : null };
}

const MONTH_ABBR = [
  'ene', 'feb', 'mar', 'abr', 'may', 'jun',
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
];

/** ISO (`2026-06-29T…`) → `'29 jun'`. */
export function formatDayMonth(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split('-');
  const idx = Number(m) - 1;
  return `${Number(d)} ${MONTH_ABBR[idx] ?? m}`;
}

export type DebtMovementKind = 'payment' | 'issuance';

export interface DebtMovement {
  id: string;
  occurredAt: string;
  label: string;
  amount: number;
  kind: DebtMovementKind;
}

const DEBT_ROLES: ReadonlySet<CategoryRole> = new Set<CategoryRole>([
  'DEBT_PAYMENT',
  'DEBT_INTEREST',
]);

/**
 * Transacciones de deuda del periodo, quedándose SÓLO con el lado ACTIVO
 * (banco) de cada movimiento — así las dos patas de un par (p. ej. "Adeudo
 * mensual de tarjeta" en BBVA ↔ "Liquidación tarjeta" en la cuenta-pasivo)
 * colapsan a un único registro reconocible en el extracto, sin duplicar.
 *
 * Una tx es de deuda si su categoría tiene rol `DEBT_PAYMENT`/`DEBT_INTEREST`
 * (un PAGO a deuda) o si es pata de un par de conversión a deuda
 * (`is_debt_pair` — dinero prestado). Clasificación:
 * - `payment`: rol de deuda (amortización de préstamo, cuota financiada,
 *   adeudo de tarjeta). Reduce la deuda.
 * - `issuance`: `is_debt_pair` sin rol de deuda (operación financiada / deuda
 *   contraída). Aumenta la deuda.
 *
 * Ordena del más reciente al más antiguo (lectura tipo extracto).
 */
export function buildDebtMovements(
  transactions: Transaction[],
  roleByCategoryId: Map<string, CategoryRole>,
  natureByAccountId: Map<string, AccountNature>,
): DebtMovement[] {
  const out: DebtMovement[] = [];
  for (const tx of transactions) {
    // Descarta la pata-pasivo: su contraparte-activo ya representa el evento.
    if (natureByAccountId.get(tx.account_id) === 'liability') continue;
    const role = tx.category_id ? roleByCategoryId.get(tx.category_id) : undefined;
    const isDebtRole = role != null && DEBT_ROLES.has(role);
    if (!isDebtRole && !tx.is_debt_pair) continue;
    out.push({
      id: tx.id,
      occurredAt: tx.occurred_at,
      label: tx.description?.trim() || 'Movimiento de deuda',
      amount: Number(tx.converted_amount ?? tx.amount),
      kind: isDebtRole ? 'payment' : 'issuance',
    });
  }
  return out.sort((a, b) => (a.occurredAt < b.occurredAt ? 1 : -1));
}

const EFFORT_LABEL: Record<DtiStatus, string> = {
  healthy: 'Saludable',
  caution: 'Precaución',
  stressed: 'Sobreendeudado',
  unknown: 'Sin datos',
};
const EFFORT_COLOR: Record<DtiStatus, string> = {
  healthy: colors.success,
  caution: colors.warning,
  stressed: colors.danger,
  unknown: colors.textSubtle,
};

/**
 * PHASE-37.2 — Resumen de deuda condensado: deuda viva + tasa de esfuerzo +
 * cuota mensual + APR medio, y debajo los MOVIMIENTOS de deuda del periodo (las
 * transacciones reales que son pago o emisión de deuda). El periodo se acota
 * con `dateFrom/dateTo`; los STOCKS (deuda viva, cuota, esfuerzo, APR) no
 * dependen del periodo.
 */
export interface DebtSummaryCardProps {
  dateFrom?: string | undefined;
  dateTo?: string | undefined;
}

export function DebtSummaryCard({ dateFrom, dateTo }: DebtSummaryCardProps = {}) {
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;
  const debtQuery = useDebtHealth(targetCurrency ? { targetCurrency } : {});
  const debt = debtQuery.data;
  const currency = debt?.reference_currency ?? storeCurrency;

  // Sólo las transacciones de DEUDA del periodo (`debt_only`): el backend
  // filtra por rol/par, así que caben de sobra en `limit` (son pocas) y no se
  // truncan las antiguas aunque el periodo tenga cientos de movimientos.
  const txQuery = useTransactions({
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
    ...(targetCurrency ? { target_currency: targetCurrency } : {}),
    debt_only: true,
    limit: 200,
  });
  const categoriesQuery = useCategories();
  const balancesQuery = useAccountBalances(targetCurrency ? { targetCurrency } : {});

  const movements = useMemo(() => {
    const roleById = new Map<string, CategoryRole>();
    for (const c of categoriesQuery.data ?? []) roleById.set(c.id, c.role);
    const natureById = new Map<string, AccountNature>();
    for (const a of balancesQuery.data?.items ?? []) natureById.set(a.account_id, a.nature);
    return buildDebtMovements(txQuery.data?.items ?? [], roleById, natureById);
  }, [txQuery.data, categoriesQuery.data, balancesQuery.data]);

  const truncated = (txQuery.data?.total ?? 0) > (txQuery.data?.items.length ?? 0);
  const movementsLoading =
    txQuery.isLoading || categoriesQuery.isLoading || balancesQuery.isLoading;

  const effort = debt?.dti_ratio;
  const status = debt?.dti_status ?? 'healthy';

  return (
    <Card style={{ padding: spacing.lg }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md }}>
        <HeartPulseIcon size={16} />
        <CardTitle>Deuda</CardTitle>
        {debt ? (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              color: EFFORT_COLOR[status],
              backgroundColor: colors.surfaceMuted,
              padding: '2px 8px',
              borderRadius: 999,
            }}
          >
            {EFFORT_LABEL[status]}
          </span>
        ) : null}
      </header>

      {debtQuery.isLoading ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>Cargando…</p>
      ) : !debt ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Sin deuda registrada.
        </p>
      ) : (
        <>
          {/* A ancho completo: número (izda) + KPIs agrupados (dcha) en una
              franja, en vez de dispersos. Envuelve en móvil/estrecho. */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'space-between',
              gap: spacing.lg,
              flexWrap: 'wrap',
            }}
          >
            <div>
              <span
                style={{
                  display: 'block',
                  fontSize: fontSize.xxl,
                  fontWeight: fontWeight.bold,
                  color: colors.text,
                  fontVariantNumeric: 'tabular-nums',
                  letterSpacing: '-0.01em',
                  lineHeight: 1.1,
                }}
              >
                {formatAmount(debt.total_liabilities, currency)}
              </span>
              <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
                deuda viva total
              </span>
            </div>
            <div style={{ display: 'flex', gap: spacing.xl, flexWrap: 'wrap' }}>
              <Kpi
                label="Tasa de esfuerzo"
                value={effort != null ? `${(effort * 100).toFixed(1)} %` : '—'}
                valueColor={EFFORT_COLOR[status]}
              />
              <Kpi label="Cuota mensual" value={formatAmount(debt.monthly_debt_payment, currency)} />
              <Kpi
                label="APR medio"
                value={debt.weighted_apr != null ? `${(debt.weighted_apr * 100).toFixed(2)} %` : '—'}
              />
            </div>
          </div>

          {/* Movimientos de deuda del periodo — las transacciones reales que son
              pago (verde) o emisión (rojo) de deuda, lado banco, sin duplicar. */}
          <div
            style={{
              marginTop: spacing.md,
              paddingTop: spacing.md,
              borderTop: `1px solid ${colors.border}`,
              display: 'flex',
              flexDirection: 'column',
              gap: spacing.xs,
            }}
          >
            <span
              style={{
                fontSize: 10,
                fontWeight: fontWeight.semibold,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color: colors.textMuted,
                marginBottom: 2,
              }}
            >
              Movimientos de deuda
            </span>

            {movementsLoading ? (
              <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>Cargando…</p>
            ) : movements.length === 0 ? (
              <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
                Sin movimientos de deuda en el periodo.
              </p>
            ) : (
              <>
                {/* Rejilla multi-columna (como el desglose): a ancho completo
                    reparte los movimientos en varias columnas, así la card queda
                    CORTA en vez de una lista larga que la hacía muy alta. */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                    columnGap: spacing.lg,
                    rowGap: spacing.xs,
                  }}
                >
                  {movements.map((m) => (
                    <MovementRow key={m.id} movement={m} currency={currency} />
                  ))}
                </div>
                {truncated ? (
                  <span style={{ fontSize: fontSize.xs, color: colors.textSubtle, marginTop: 2 }}>
                    Puede faltar alguno antiguo — acota el periodo para verlos todos.
                  </span>
                ) : null}
              </>
            )}
          </div>
        </>
      )}
    </Card>
  );
}

function MovementRow({ movement, currency }: { movement: DebtMovement; currency: string }) {
  const [hovered, setHovered] = useState(false);
  const isIssuance = movement.kind === 'issuance';
  const accent = isIssuance ? colors.danger : colors.success;
  const accentSoft = isIssuance ? colors.dangerSoft : colors.successSoft;
  const Icon = isIssuance ? TrendingUpIcon : TrendingDownIcon;
  const { main, ref4 } = splitDebtLabel(movement.label);
  const amountText = `${isIssuance ? '+' : ''}${formatAmount(String(movement.amount.toFixed(2)), currency)}`;
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `6px ${spacing.sm}px`,
        borderRadius: radius.sm,
        backgroundColor: hovered ? colors.surfaceMuted : 'transparent',
        transition: 'background-color 120ms ease',
      }}
    >
      {/* Chip tonal: ↓ verde (pago, baja la deuda) / ↑ rojo (emisión, sube). */}
      <span
        aria-hidden
        style={{
          width: 30,
          height: 30,
          borderRadius: radius.sm,
          backgroundColor: accentSoft,
          color: accent,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: '0 0 auto',
        }}
      >
        <Icon size={15} />
      </span>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: colors.text,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={movement.label}
        >
          {main}
        </span>
        <span
          style={{
            fontSize: fontSize.xs,
            color: colors.textMuted,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {formatDayMonth(movement.occurredAt)}
          {ref4 ? ` · ····${ref4}` : ''}
        </span>
      </div>

      <span
        style={{
          flex: '0 0 auto',
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: accent,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {amountText}
      </span>
    </div>
  );
}

function Kpi({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <span
        style={{
          fontSize: 10,
          fontWeight: fontWeight.semibold,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: colors.textMuted,
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
        }}
      >
        {value}
      </span>
    </div>
  );
}
