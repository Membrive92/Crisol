'use client';

import { useMemo, useState } from 'react';

import { useAccountBalances, useCategories, useTransactions } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { AccountNature, CategoryRole, Transaction } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card, CardTitle } from '@/components/ui/card';
import { TrendingDownIcon, TrendingUpIcon } from '@/components/ui/icons';

export interface DebtMovementsCardProps {
  /** Rango activo (ISO) del período de `/debt`. */
  dateFrom?: string | undefined;
  dateTo?: string | undefined;
  currency: string;
}

type DebtMovementKind = 'payment' | 'issuance';

interface DebtMovement {
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

/**
 * Separa la descripción bancaria en parte legible + últimos 4 dígitos de la
 * referencia final (nº de cuenta/tarjeta), para de-enfatizar el número largo.
 */
export function splitDebtLabel(description: string): { main: string; ref4: string | null } {
  const m = description.match(/^(.*?)[\s:]*(\d[\d\-/ ]{4,}\d)\s*$/);
  const main = m?.[1]?.trim();
  if (!m || !main) return { main: description.trim(), ref4: null };
  const digits = (m[2] ?? '').replace(/\D/g, '');
  return { main, ref4: digits.length >= 4 ? digits.slice(-4) : null };
}

/**
 * Transacciones de deuda del periodo, quedándose SÓLO con el lado ACTIVO
 * (banco) de cada movimiento — las dos patas de un par colapsan a un registro
 * reconocible en el extracto, sin duplicar. `payment` (rol de deuda, baja la
 * deuda) vs `issuance` (par de conversión sin rol, la sube). Más reciente
 * primero (lectura tipo extracto).
 */
export function buildDebtMovements(
  transactions: Transaction[],
  roleByCategoryId: Map<string, CategoryRole>,
  natureByAccountId: Map<string, AccountNature>,
): DebtMovement[] {
  const out: DebtMovement[] = [];
  for (const tx of transactions) {
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

/**
 * PHASE-43.5 (ADR-0006) — Movimientos de deuda del periodo (pagos y emisiones),
 * el DETALLE-flujo que antes vivía en `DebtSummaryCard` de Análisis. Su sitio
 * es `/debt`, junto al cuadro y los KPIs de deuda; responde *"¿qué pagué/emití
 * de deuda este periodo?"*. El gauge y los KPIs NO se replican aquí (ya están
 * arriba en la página).
 */
export function DebtMovementsCard({ dateFrom, dateTo, currency }: DebtMovementsCardProps) {
  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;

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
  const isLoading =
    txQuery.isLoading || categoriesQuery.isLoading || balancesQuery.isLoading;

  return (
    <Card style={{ padding: spacing.lg }}>
      <CardTitle style={{ marginBottom: spacing.md }}>Movimientos de deuda</CardTitle>
      {isLoading ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>Cargando…</p>
      ) : movements.length === 0 ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Sin movimientos de deuda en el periodo.
        </p>
      ) : (
        <>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              columnGap: spacing.lg,
              rowGap: spacing.xs,
            }}
          >
            {movements.map((m) => (
              <MovementRow key={m.id} movement={m} currency={currency} />
            ))}
          </div>
          {truncated ? (
            <span style={{ fontSize: fontSize.xs, color: colors.textSubtle, marginTop: spacing.xs, display: 'block' }}>
              Puede faltar alguno antiguo — acota el periodo para verlos todos.
            </span>
          ) : null}
        </>
      )}
    </Card>
  );
}

/** Tope de la etiqueta: las largas se truncan aquí; las cortas ocupan su ancho
 * natural. El importe se pega justo después con la separación de la fila, así
 * que NUNCA flota lejos del texto (ni con etiquetas cortas ni largas). */
const LABEL_MAX_WIDTH = 200;

function MovementRow({ movement, currency }: { movement: DebtMovement; currency: string }) {
  const [hovered, setHovered] = useState(false);
  const isIssuance = movement.kind === 'issuance';
  const accent = isIssuance ? colors.danger : colors.success;
  const accentSoft = isIssuance ? colors.dangerSoft : colors.successSoft;
  const Icon = isIssuance ? TrendingUpIcon : TrendingDownIcon;
  const { main, ref4 } = splitDebtLabel(movement.label);
  // Importe en estilo UNIFORME (color neutro, sin signo): la dirección
  // (amortización ↓ / emisión ↑) ya la lleva el icono de color de la izquierda,
  // así que todos los números de la lista se leen igual.
  const amountText = formatAmount(String(movement.amount.toFixed(2)), currency);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        flex: '0 0 auto',
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `6px ${spacing.sm}px`,
        borderRadius: radius.sm,
        backgroundColor: hovered ? colors.surfaceMuted : 'transparent',
        transition: 'background-color 120ms ease',
      }}
    >
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
      <div style={{ flex: '0 1 auto', maxWidth: LABEL_MAX_WIDTH, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
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
        <span style={{ fontSize: fontSize.xs, color: colors.textMuted, fontVariantNumeric: 'tabular-nums' }}>
          {formatDayMonth(movement.occurredAt)}
          {ref4 ? ` · ····${ref4}` : ''}
        </span>
      </div>
      <span
        style={{
          flex: '0 0 auto',
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {amountText}
      </span>
    </div>
  );
}
