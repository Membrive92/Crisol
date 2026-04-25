'use client';

import { useState } from 'react';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import type { CategoryBreakdownItem, CategoryKind } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { Card } from '@/components/ui/card';

export interface CategoryDonutProps {
  data: CategoryBreakdownItem[] | undefined;
  currency: string;
  isLoading: boolean;
  kind: CategoryKind;
  onKindChange: (next: CategoryKind) => void;
}

const PALETTE = [
  '#1976d2',
  '#d32f2f',
  '#2e7d32',
  '#ed6c02',
  '#7b1fa2',
  '#0288d1',
  '#c2185b',
  '#5d4037',
  '#455a64',
  '#558b2f',
];

export function CategoryDonut({
  data,
  currency,
  isLoading,
  kind,
  onKindChange,
}: CategoryDonutProps) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const chartData = (data ?? []).map((item, idx) => ({
    name: item.category_name,
    value: Number(item.total),
    color: PALETTE[idx % PALETTE.length] ?? colors.primary,
    id: item.category_id ?? `_no_cat_${idx}`,
  }));

  const visible = chartData.filter((d) => !hidden.has(d.id));
  const empty = !isLoading && visible.length === 0;

  return (
    <Card>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.md,
          gap: spacing.sm,
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
          Por categoría
        </h2>
        <KindToggle value={kind} onChange={onKindChange} />
      </header>
      {isLoading && !data ? (
        <p style={{ color: colors.textMuted, margin: 0 }}>Cargando…</p>
      ) : empty ? (
        <p style={{ color: colors.textMuted, margin: 0 }}>Sin datos en el periodo.</p>
      ) : (
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={visible}
                dataKey="value"
                nameKey="name"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
              >
                {visible.map((d) => (
                  <Cell key={d.id} fill={d.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => formatAmount(String(value ?? 0), currency)}
                contentStyle={{
                  backgroundColor: colors.surface,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 6,
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, cursor: 'pointer' }}
                onClick={(entry) => {
                  const id = (entry as { payload?: { id?: string } }).payload?.id;
                  if (!id) return;
                  setHidden((prev) => {
                    const next = new Set(prev);
                    if (next.has(id)) next.delete(id);
                    else next.add(id);
                    return next;
                  });
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function KindToggle({
  value,
  onChange,
}: {
  value: CategoryKind;
  onChange: (next: CategoryKind) => void;
}) {
  return (
    <div
      style={{
        display: 'inline-flex',
        border: `1px solid ${colors.border}`,
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      <ToggleButton active={value === 'expense'} onClick={() => onChange('expense')}>
        Gastos
      </ToggleButton>
      <ToggleButton active={value === 'income'} onClick={() => onChange('income')}>
        Ingresos
      </ToggleButton>
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: `${spacing.xs}px ${spacing.sm}px`,
        backgroundColor: active ? colors.primary : colors.surface,
        color: active ? colors.surface : colors.text,
        border: 'none',
        cursor: 'pointer',
        fontSize: fontSize.xs,
        fontWeight: fontWeight.medium,
      }}
    >
      {children}
    </button>
  );
}
