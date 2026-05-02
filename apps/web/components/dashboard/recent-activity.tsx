'use client';

import Link from 'next/link';

import { useTransactions } from '@finanzas/services';
import type { Transaction } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

const RECENT_LIMIT = 5;

/**
 * Sidebar de "Actividad reciente". Muestra las últimas N transacciones
 * del usuario (de cualquier moneda — la moneda viene en cada item).
 * Click en una fila navega al detalle.
 */
export function RecentActivity() {
  const { data, isLoading, isError } = useTransactions({ limit: RECENT_LIMIT });
  const items = data?.items ?? [];

  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <header
        style={{
          padding: spacing.md,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          borderBottom: `1px solid ${colors.border}`,
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
          Actividad reciente
        </h2>
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

      {isLoading ? (
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
      ) : isError ? (
        <p
          style={{
            margin: 0,
            padding: spacing.md,
            color: colors.danger,
            fontSize: fontSize.sm,
          }}
        >
          No se pudo cargar la actividad reciente.
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
          Aún no hay movimientos. Crea uno desde el botón ＋ o sube un ticket.
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
              <ActivityRow tx={tx} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ActivityRow({ tx }: { tx: Transaction }) {
  // El `amount` se guarda siempre positivo en BD; la dirección la marca
  // el `kind` de la categoría. En la sidebar (compacta) no diferenciamos
  // ingreso/gasto vía signo — el detalle de la transacción ya lo aclara.
  const occurred = new Date(tx.occurred_at);
  const dateLabel = occurred.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
  });

  return (
    <Link
      href={`/personal-finance/transactions/${tx.id}` as never}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: `${spacing.sm + 2}px ${spacing.md}px`,
        textDecoration: 'none',
        gap: spacing.sm,
      }}
    >
      <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: colors.text,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {tx.description ?? 'Movimiento'}
        </span>
        <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          {dateLabel}
        </span>
      </div>
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatAmount(tx.amount, tx.currency)}
      </span>
    </Link>
  );
}
