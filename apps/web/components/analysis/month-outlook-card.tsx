'use client';

import { useState } from 'react';

import type { MonthOutlookResponse } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { Card, CardTitle } from '@/components/ui/card';

export interface MonthOutlookCardProps {
  data: MonthOutlookResponse | undefined;
  currency: string;
  isLoading: boolean;
}

/** Semáforo del runway (umbrales de fondo de emergencia, orientativos). */
function runwayTone(months: number): { color: string; label: string } {
  if (months < 3) return { color: colors.danger, label: 'ajustado' };
  if (months < 6) return { color: colors.warning, label: 'razonable' };
  return { color: colors.success, label: 'holgado' };
}

/**
 * PHASE-37.4 — Proyección de fin de mes: cuánto queda comprometido este mes
 * (gastos fijos + cuotas) y el colchón/runway (meses que tu liquidez cubre
 * tu gasto estructural). Lista de cargos expandible.
 */
export function MonthOutlookCard({ data, currency, isLoading }: MonthOutlookCardProps) {
  const [expanded, setExpanded] = useState(false);
  const ref = data?.reference_currency ?? currency;
  const items = data?.committed_items ?? [];
  const runway = data?.runway_months ?? null;
  const tone = runway !== null ? runwayTone(runway) : null;

  return (
    <Card style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: spacing.sm }}>
        <CardTitle size="sm">Fin de mes</CardTitle>
        {data ? (
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {data.days_remaining} {data.days_remaining === 1 ? 'día' : 'días'} restantes
          </span>
        ) : null}
      </header>

      {isLoading && !data ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>Calculando…</p>
      ) : (
        <>
          {/* Comprometido restante */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 10, fontWeight: fontWeight.semibold, letterSpacing: '0.05em', textTransform: 'uppercase', color: colors.textMuted }}>
              Comprometido restante
            </span>
            <span style={{ fontSize: fontSize.xl, fontWeight: fontWeight.bold, color: colors.text, fontVariantNumeric: 'tabular-nums' }}>
              {data ? formatAmount(data.committed_remaining, ref) : '—'}
            </span>
            <span style={{ fontSize: 10, color: colors.textSubtle }}>
              {items.length} {items.length === 1 ? 'cargo previsto' : 'cargos previstos'}
            </span>
          </div>

          {/* Runway */}
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, padding: `${spacing.sm}px ${spacing.md}px`, borderRadius: radius.sm, backgroundColor: colors.surfaceMuted }}>
            <span aria-hidden style={{ width: 8, height: 8, borderRadius: 999, backgroundColor: tone?.color ?? colors.textSubtle, flexShrink: 0 }} />
            <span style={{ fontSize: fontSize.sm, color: colors.text }}>
              {runway !== null ? (
                <>
                  Colchón:{' '}
                  <strong>{runway > 99 ? '99+' : runway.toFixed(1)} meses</strong> de gasto
                  estructural <span style={{ color: colors.textMuted }}>({tone?.label})</span>
                </>
              ) : (
                <span style={{ color: colors.textMuted }}>
                  Colchón no disponible — sin gasto estructural o saldo líquido en negativo.
                </span>
              )}
            </span>
          </div>

          {/* Lista de cargos */}
          {items.length > 0 ? (
            <div>
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, fontSize: fontSize.xs, fontWeight: fontWeight.medium, color: colors.primary }}
                aria-expanded={expanded}
              >
                {expanded ? 'Ocultar' : 'Ver'} cargos previstos
              </button>
              {expanded ? (
                <ul style={{ listStyle: 'none', margin: `${spacing.sm}px 0 0 0`, padding: 0, display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
                  {items.map((it, i) => (
                    <li key={`${it.name}-${it.expected_date}-${i}`} style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, fontSize: fontSize.sm }}>
                      <span style={{ minWidth: 44, fontVariantNumeric: 'tabular-nums', color: colors.textMuted, fontSize: fontSize.xs }}>
                        {it.expected_date.slice(5)}
                      </span>
                      <span style={{ flex: 1, minWidth: 0, color: colors.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {it.name}
                        {it.overdue ? (
                          <span style={{ marginLeft: 6, fontSize: 10, fontWeight: fontWeight.semibold, color: colors.danger }}>ATRASADO</span>
                        ) : null}
                      </span>
                      <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: fontWeight.semibold, color: colors.text }}>
                        {formatAmount(it.amount, ref)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
              Nada comprometido en lo que queda de mes.
            </p>
          )}
        </>
      )}
    </Card>
  );
}
