'use client';

import Link from 'next/link';

import { useCategories, useTransactions } from '@crisol/services';
import type { Category, CategoryKind, Transaction, TransactionFlow } from '@crisol/types';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';
import { formatAmount } from '@crisol/ui';

import { iconForTransaction } from '@/lib/category-icons';
import { Card } from '@/components/ui/card';
import { PlusIcon } from '@/components/ui/icons';

const RECENT_LIMIT = 4;

/**
 * Sidebar de "Actividad reciente" estilo Stitch. Cada fila tiene:
 * icono cuadrado (derivado de la descripción/categoría), descripción,
 * fecha relativa, e importe a la derecha en color por kind. Pie con
 * botón "+ Añadir transacción" filled primary.
 */
export function StitchRecentActivity() {
  const txQuery = useTransactions({ limit: RECENT_LIMIT });
  const catQuery = useCategories();
  const items = txQuery.data?.items ?? [];
  const categories = catQuery.data ?? [];

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <header
        style={{
          padding: spacing.md,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Actividad reciente
        </h3>
        <Link
          href="/personal-finance/transactions"
          style={{
            fontSize: fontSize.xs,
            fontWeight: fontWeight.semibold,
            color: colors.primary,
            textDecoration: 'none',
          }}
        >
          Ver todas →
        </Link>
      </header>

      {txQuery.isLoading ? (
        <p
          style={{
            margin: 0,
            padding: spacing.md,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          Cargando…
        </p>
      ) : items.length === 0 ? (
        <p
          style={{
            margin: 0,
            padding: spacing.md,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          Aún no hay movimientos.
        </p>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
          {items.map((tx, idx) => (
            <li
              key={tx.id}
              style={{
                borderTop: idx === 0 ? 'none' : `1px solid ${colors.border}`,
              }}
            >
              <ActivityRow tx={tx} category={findCategory(categories, tx.category_id)} />
            </li>
          ))}
        </ul>
      )}

      <div
        style={{
          padding: spacing.md,
          backgroundColor: colors.surfaceMuted,
          borderTop: `1px solid ${colors.border}`,
        }}
      >
        <Link
          href="/personal-finance/transactions/new"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: spacing.xs,
            width: '100%',
            padding: `${spacing.sm}px 0`,
            backgroundColor: colors.primary,
            color: colors.onPrimary,
            border: 'none',
            borderRadius: 8,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            textDecoration: 'none',
          }}
        >
          <PlusIcon size={16} />
          Añadir Transacción
        </Link>
      </div>
    </Card>
  );
}

// ADR-0004 (AUDIT-2026-07): el signo/color lo manda `tx.flow`, no la
// categoría. IN→income, OUT→expense, TRANSFER_*→neutro. `undefined` → sin
// flow, usar fallback por categoría (fila heredada).
function kindFromFlow(
  flow: TransactionFlow | null | undefined,
): CategoryKind | null | undefined {
  if (flow === 'IN') return 'income';
  if (flow === 'OUT') return 'expense';
  if (flow === 'TRANSFER_IN' || flow === 'TRANSFER_OUT') return null;
  return undefined;
}

function ActivityRow({ tx, category }: { tx: Transaction; category: Category | undefined }) {
  const Icon = iconForTransaction(tx.description, category?.name);
  // ADR-0004: el signo/color lo manda `tx.flow`. Una pata de
  // transferencia/deuda (TRANSFER_*) es neutra — sin esto, la pata-activo de
  // una operación financiada (categoría income) saldría como "+824,77 €"
  // verde en el dashboard. Fallback por categoría sólo si la fila no tiene flow.
  const flowKind = kindFromFlow(tx.flow);
  const isTransferLike =
    tx.transfer_pair_id !== null || category?.is_transfer === true;
  const displayKind =
    flowKind !== undefined
      ? flowKind
      : isTransferLike
        ? null
        : (category?.kind ?? null);
  const amountColor = displayKind === 'income' ? colors.success : colors.text;
  const sign =
    displayKind === 'income' ? '+' : displayKind === 'expense' ? '-' : '';

  return (
    <Link
      href={`/personal-finance/transactions/${tx.id}` as never}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.md,
        padding: `${spacing.sm + 2}px ${spacing.md}px`,
        textDecoration: 'none',
      }}
    >
      <div
        aria-hidden
        style={{
          width: 36,
          height: 36,
          borderRadius: 8,
          backgroundColor: colors.surfaceMuted,
          color: colors.textMuted,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: '0 0 auto',
        }}
      >
        <Icon size={18} />
      </div>
      <div style={{ minWidth: 0, flex: 1, display: 'flex', flexDirection: 'column' }}>
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {tx.description ?? 'Movimiento'}
        </span>
        <span style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>
          {formatRelative(tx.occurred_at)}
        </span>
      </div>
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: amountColor,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {sign}
        {formatAmount(tx.amount, tx.currency)}
      </span>
    </Link>
  );
}

function findCategory(categories: Category[], id: string | null): Category | undefined {
  if (!id) return undefined;
  return categories.find((c) => c.id === id);
}

function formatRelative(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 1) {
    return `Hoy, ${date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;
  }
  if (diffDays === 1) return 'Ayer';
  if (diffDays < 7) return `${diffDays} días`;
  return date.toLocaleDateString(undefined, { day: '2-digit', month: 'short' });
}
