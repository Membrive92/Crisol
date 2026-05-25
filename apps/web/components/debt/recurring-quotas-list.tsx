'use client';

import Link from 'next/link';

import type { RecurringQuotaRef } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';

export interface RecurringQuotasListProps {
  items: RecurringQuotaRef[];
  currency: string;
  isLoading: boolean;
}

/**
 * PHASE-30.3 — Lista de "Cuotas recurrentes detectadas" — fixed
 * expenses confirmados cuya categoría tiene `role IN (DEBT_PAYMENT,
 * DEBT_INTEREST)`. Si el detector las detectó pero el usuario no
 * tiene un contrato (liability account) vinculado a esa categoría,
 * la sección sirve como entrada al CTA "Vincular contrato" de
 * Capa 2 (la lógica de matching vive en `/debt/contracts` — link
 * a `/settings/accounts` durante 30.3).
 */
export function RecurringQuotasList({
  items,
  currency,
  isLoading,
}: RecurringQuotasListProps) {
  if (isLoading) {
    return (
      <Card style={{ padding: spacing.md }}>
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Cargando cuotas detectadas…
        </p>
      </Card>
    );
  }

  if (items.length === 0) return null;

  return (
    <Card
      style={{
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <header>
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            letterSpacing: '-0.01em',
          }}
        >
          Cuotas recurrentes detectadas
        </h2>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.xs,
            color: colors.textMuted,
            lineHeight: 1.5,
          }}
        >
          Gastos fijos que estás confirmando como pagos a deuda. Si
          alguno tiene un contrato real (hipoteca, préstamo), vincúlalo
          a una cuenta para que su saldo cuente en tu patrimonio.
        </p>
      </header>

      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.xs,
        }}
      >
        {items.map((q) => (
          <li
            key={q.fixed_expense_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing.md,
              padding: `${spacing.sm}px ${spacing.md}px`,
              backgroundColor: colors.surfaceMuted,
              border: `1px solid ${colors.border}`,
              borderRadius: radius.sm,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: fontSize.sm,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {q.merchant}
              </div>
              {q.category_name ? (
                <div
                  style={{
                    fontSize: 11,
                    color: colors.textMuted,
                    marginTop: 1,
                  }}
                >
                  {q.category_name}
                </div>
              ) : null}
            </div>
            <div
              style={{
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                color: colors.text,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {formatAmount(q.amount, q.currency || currency)}
              <span
                style={{
                  fontSize: fontSize.xs,
                  fontWeight: fontWeight.regular,
                  color: colors.textMuted,
                  marginLeft: 4,
                }}
              >
                / mes
              </span>
            </div>
            <Link
              href="/settings/accounts"
              style={{
                fontSize: fontSize.xs,
                fontWeight: fontWeight.semibold,
                color: colors.primary,
                textDecoration: 'none',
                padding: `${spacing.xs}px ${spacing.sm}px`,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.sm,
              }}
            >
              Vincular
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
