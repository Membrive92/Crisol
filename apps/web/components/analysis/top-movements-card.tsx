'use client';

import type { AnalyticsTxRef } from '@crisol/types';
import {
  categoryRowAmount,
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  isRefundInExpenseList,
  radius,
  spacing,
} from '@crisol/ui';

import { iconForCategoryName } from '@/lib/category-icons';
import { Card } from '@/components/ui/card';

export interface TopMovementsCardProps {
  /** Mayores gastos PUNTUALES del periodo (`structure.top_exceptional`). */
  items: AnalyticsTxRef[];
  currency: string;
  isLoading: boolean;
}

/** `YYYY-MM-DDTHH:mm:ssZ` → `DD/MM`. */
function shortDay(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

/**
 * PHASE-43.3 — "Top movimientos del periodo". Responde *"¿qué pasó este mes?"*
 * en cinco líneas: los mayores gastos puntuales del rango, más rápido de leer
 * que el donut. Usa `top_exceptional`, que el backend ya calculaba y ninguna
 * vista mostraba. Componente tonto: recibe todo por props.
 */
export function TopMovementsCard({ items, currency, isLoading }: TopMovementsCardProps) {
  return (
    <Card style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column' }}>
      <h3
        style={{
          margin: 0,
          marginBottom: spacing.lg,
          fontSize: fontSize.lg,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        Top movimientos del periodo
      </h3>
      {isLoading ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>Cargando…</p>
      ) : items.length === 0 ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin gastos puntuales destacados en el periodo.
        </p>
      ) : (
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
          {items.map((tx) => (
            <MovementRow key={tx.id} tx={tx} currency={currency} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function MovementRow({ tx, currency }: { tx: AnalyticsTxRef; currency: string }) {
  const label = tx.description?.trim() || tx.category_name || 'Movimiento';
  const Icon = iconForCategoryName(tx.category_name ?? label);
  // PHASE-47.H — esta lista es el cubo de GASTO (`_is_expense()`), que incluye
  // las devoluciones, y ordena por el importe SIN signo: sin esto un reembolso
  // de 79 € se presenta como el mayor gasto puntual del mes, mientras el
  // desglose de dos tarjetas más allá lo resta de su categoría.
  const devolucion = isRefundInExpenseList(tx.flow);
  const amount = categoryRowAmount(tx.converted_amount ?? tx.amount, tx.flow, 'expense');
  return (
    <li style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
      <span
        aria-hidden
        style={{
          width: 32,
          height: 32,
          borderRadius: radius.sm,
          backgroundColor: colors.surfaceMuted,
          color: colors.textMuted,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: '0 0 auto',
          border: `1px solid ${colors.border}`,
        }}
      >
        <Icon size={16} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: colors.text,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </div>
        <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
          {devolucion ? 'Devolución · ' : ''}
          {shortDay(tx.occurred_at)}
          {tx.category_name ? ` · ${tx.category_name}` : ''}
        </div>
      </div>
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: devolucion ? colors.success : colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatAmount(amount, currency)}
      </span>
    </li>
  );
}
