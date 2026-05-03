'use client';

import { useState } from 'react';

import type { MonthlyBucket } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

const SHORT_MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

export interface StitchIncomeVsExpensesProps {
  data: MonthlyBucket[];
  currency: string;
  isLoading: boolean;
}

/**
 * Bar chart Income vs Expenses al estilo Stitch — barras apiladas
 * por mes (ingreso encima, gasto debajo), 12 buckets, sin libs
 * externas. Hover muestra los valores absolutos.
 */
export function StitchIncomeVsExpenses({
  data,
  currency,
  isLoading,
}: StitchIncomeVsExpensesProps) {
  const max = Math.max(
    ...data.map((b) => Math.max(Number(b.income), Number(b.expenses))),
    1,
  );
  const empty = !isLoading && data.every((b) => Number(b.income) === 0 && Number(b.expenses) === 0);

  return (
    <Card style={{ padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.lg,
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: fontSize.lg,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          Income vs Expenses
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
          <Legend color={colors.success} label="Ingresos" />
          <Legend color={colors.danger} label="Gastos" />
        </div>
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin datos en el periodo.
        </p>
      ) : (
        <>
          <div
            style={{
              position: 'relative',
              height: 240,
              display: 'flex',
              alignItems: 'flex-end',
              gap: 6,
            }}
          >
            {/* Líneas de cuadrícula */}
            <div
              aria-hidden
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                pointerEvents: 'none',
                opacity: 0.15,
              }}
            >
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} style={{ borderTop: `1px dashed ${colors.text}` }} />
              ))}
            </div>

            {data.map((bucket) => (
              <BucketBar
                key={bucket.month}
                income={Number(bucket.income)}
                expenses={Number(bucket.expenses)}
                max={max}
                currency={currency}
              />
            ))}
          </div>
          <div style={{ display: 'flex', marginTop: spacing.sm, paddingLeft: 4 }}>
            {data.map((bucket) => {
              const monthIdx = parseInt(bucket.month.slice(5, 7), 10) - 1;
              return (
                <span
                  key={bucket.month}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    fontSize: fontSize.xs,
                    color: colors.textSubtle,
                  }}
                >
                  {SHORT_MONTHS[monthIdx] ?? bucket.month}
                </span>
              );
            })}
          </div>
        </>
      )}
    </Card>
  );
}

function BucketBar({
  income,
  expenses,
  max,
  currency,
}: {
  income: number;
  expenses: number;
  max: number;
  currency: string;
}) {
  const [hovered, setHovered] = useState(false);
  const incomePct = (income / max) * 100;
  const expensePct = (expenses / max) * 100;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        flex: 1,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
        gap: 2,
        position: 'relative',
        cursor: 'default',
      }}
    >
      {hovered ? (
        <span
          style={{
            position: 'absolute',
            top: -50,
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.sm,
            padding: '6px 10px',
            fontSize: 11,
            color: colors.text,
            whiteSpace: 'nowrap',
            zIndex: 5,
            pointerEvents: 'none',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.32)',
          }}
        >
          <div style={{ color: colors.success }}>+ {formatAmount(String(income.toFixed(2)), currency)}</div>
          <div style={{ color: colors.danger }}>− {formatAmount(String(expenses.toFixed(2)), currency)}</div>
        </span>
      ) : null}
      <div
        style={{
          height: `${incomePct}%`,
          backgroundColor: hovered ? colors.success : `${colors.success}33`,
          borderTopLeftRadius: 3,
          borderTopRightRadius: 3,
          transition: 'background-color 120ms ease',
          minHeight: income > 0 ? 2 : 0,
        }}
      />
      <div
        style={{
          height: `${expensePct}%`,
          backgroundColor: hovered ? colors.danger : `${colors.danger}33`,
          borderBottomLeftRadius: 3,
          borderBottomRightRadius: 3,
          transition: 'background-color 120ms ease',
          minHeight: expenses > 0 ? 2 : 0,
        }}
      />
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: '50%',
          backgroundColor: color,
        }}
      />
      <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>{label}</span>
    </span>
  );
}
