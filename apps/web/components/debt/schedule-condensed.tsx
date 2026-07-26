'use client';

import { useMemo, useState } from 'react';

import type { AmortizationRow } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

export interface ScheduleCondensedProps {
  rows: AmortizationRow[];
  currency: string;
  /** Render personalizado por fila — sirve para inyectar el botón de
   * "Pagar" / "Editar" del editor existente sin recrear la lógica
   * dentro de este componente. */
  renderRow?: (row: AmortizationRow) => React.ReactNode;
}

interface YearBucket {
  year: number;
  totalPayment: number;
  totalInterest: number;
  totalPrincipal: number;
  closingBalance: string;
  paidCount: number;
  rows: AmortizationRow[];
}

const SPANISH_MONTHS = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

/**
 * PHASE-30.4 — Vista condensada del cuadro francés agrupada por año.
 *
 * Una fila resumen por año (totales pagados + saldo al cierre), con
 * desplegable que muestra las 12 cuotas del año. Mucho más
 * navegable para hipotecas de 240-360 meses que el listado plano.
 *
 * El año en curso se marca con borde primary; el mes en curso dentro
 * del año expandido recibe fondo `surfaceMuted`.
 */
export function ScheduleCondensed({
  rows,
  currency,
  renderRow,
}: ScheduleCondensedProps) {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonthIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

  const buckets = useMemo<YearBucket[]>(() => {
    const byYear = new Map<number, AmortizationRow[]>();
    for (const row of rows) {
      const y = new Date(`${row.due_date}T00:00:00Z`).getUTCFullYear();
      const arr = byYear.get(y) ?? [];
      arr.push(row);
      byYear.set(y, arr);
    }
    return Array.from(byYear.entries())
      .sort(([a], [b]) => a - b)
      .map(([year, yearRows]) => {
        const sorted = [...yearRows].sort((a, b) =>
          a.due_date.localeCompare(b.due_date),
        );
        const totalPayment = sorted.reduce((s, r) => s + Number(r.payment), 0);
        const totalInterest = sorted.reduce((s, r) => s + Number(r.interest), 0);
        const totalPrincipal = sorted.reduce(
          (s, r) => s + Number(r.principal),
          0,
        );
        const last = sorted[sorted.length - 1];
        const paidCount = sorted.filter((r) => r.paid_at != null).length;
        return {
          year,
          totalPayment,
          totalInterest,
          totalPrincipal,
          closingBalance: last?.remaining_balance ?? '0',
          paidCount,
          rows: sorted,
        };
      });
  }, [rows]);

  const [expanded, setExpanded] = useState<Set<number>>(() => new Set([currentYear]));

  function toggle(year: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(year)) next.delete(year);
      else next.add(year);
      return next;
    });
  }

  return (
    <ul
      style={{
        margin: 0,
        padding: 0,
        listStyle: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      {buckets.map((bucket) => {
        const isCurrent = bucket.year === currentYear;
        const isOpen = expanded.has(bucket.year);
        return (
          <li
            key={bucket.year}
            style={{
              borderRadius: radius.md,
              border: `1px solid ${isCurrent ? colors.primary : colors.border}`,
              backgroundColor: colors.surface,
              overflow: 'hidden',
            }}
          >
            <button
              type="button"
              onClick={() => toggle(bucket.year)}
              aria-expanded={isOpen}
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: `${spacing.sm}px ${spacing.md}px`,
                display: 'grid',
                gridTemplateColumns: '60px 1fr auto auto',
                gap: spacing.md,
                alignItems: 'center',
                textAlign: 'left',
              }}
            >
              <span
                style={{
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.bold,
                  color: colors.text,
                  letterSpacing: '-0.01em',
                }}
              >
                {bucket.year}
              </span>
              <span
                style={{
                  fontSize: fontSize.xs,
                  color: colors.textMuted,
                  lineHeight: 1.4,
                }}
              >
                {formatAmount(bucket.totalPayment.toFixed(2), currency)}{' '}
                pagado · {formatAmount(bucket.totalInterest.toFixed(2), currency)}{' '}
                intereses
                {bucket.paidCount > 0 ? (
                  <>
                    {' · '}
                    <strong style={{ color: colors.success }}>
                      {bucket.paidCount}/{bucket.rows.length} pagadas
                    </strong>
                  </>
                ) : null}
              </span>
              <span
                style={{
                  fontSize: fontSize.sm,
                  fontWeight: fontWeight.semibold,
                  color: colors.text,
                  fontVariantNumeric: 'tabular-nums',
                  textAlign: 'right',
                }}
                title="Saldo pendiente al cierre del año"
              >
                {formatAmount(bucket.closingBalance, currency)}
              </span>
              <span
                aria-hidden
                style={{
                  fontSize: fontSize.lg,
                  color: colors.textMuted,
                  transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 120ms ease',
                }}
              >
                ▾
              </span>
            </button>

            {isOpen ? (
              <div style={{ borderTop: `1px solid ${colors.border}` }}>
                <div style={{ overflowX: 'auto' }}>
                <table
                  style={{
                    width: '100%',
                    minWidth: 520,
                    borderCollapse: 'collapse',
                    fontSize: fontSize.xs,
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        backgroundColor: colors.surfaceMuted,
                        color: colors.textMuted,
                      }}
                    >
                      <Th align="left">Mes</Th>
                      <Th align="right">Cuota</Th>
                      <Th align="right">Intereses</Th>
                      <Th align="right">Capital</Th>
                      <Th align="right">Saldo</Th>
                      {renderRow ? <Th align="right">Acciones</Th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {bucket.rows.map((row) => {
                      const monthIdx = new Date(
                        `${row.due_date}T00:00:00Z`,
                      ).getUTCMonth();
                      const monthIso = row.due_date.slice(0, 7);
                      const isCurrentMonth = monthIso === currentMonthIso;
                      const isPaid = row.paid_at != null;
                      return (
                        <tr
                          key={`${bucket.year}-${row.month}`}
                          style={{
                            backgroundColor: isCurrentMonth
                              ? colors.surfaceMuted
                              : 'transparent',
                            color: isPaid ? colors.textMuted : colors.text,
                          }}
                        >
                          <Td align="left">
                            {SPANISH_MONTHS[monthIdx]} · cuota {row.month}
                            {isPaid ? ' · ✓' : ''}
                          </Td>
                          <Td align="right">
                            {formatAmount(row.payment, currency)}
                          </Td>
                          <Td align="right" muted>
                            {formatAmount(row.interest, currency)}
                          </Td>
                          <Td align="right">
                            {formatAmount(row.principal, currency)}
                          </Td>
                          <Td align="right" muted>
                            {formatAmount(row.remaining_balance, currency)}
                          </Td>
                          {renderRow ? (
                            <Td align="right">{renderRow(row)}</Td>
                          ) : null}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function Th({
  children,
  align,
}: {
  children: React.ReactNode;
  align: 'left' | 'right';
}) {
  return (
    <th
      style={{
        textAlign: align,
        fontWeight: fontWeight.semibold,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        fontSize: 10,
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align,
  muted,
}: {
  children: React.ReactNode;
  align: 'left' | 'right';
  muted?: boolean;
}) {
  return (
    <td
      style={{
        textAlign: align,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        borderTop: `1px solid ${colors.border}`,
        color: muted ? colors.textMuted : undefined,
        fontVariantNumeric: align === 'right' ? 'tabular-nums' : undefined,
      }}
    >
      {children}
    </td>
  );
}
