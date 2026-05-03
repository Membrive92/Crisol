'use client';

import type { CategoryBreakdownItem } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';
import { formatAmount } from '@finanzas/ui';

import { iconForCategoryName } from '@/lib/category-icons';
import { Card } from '@/components/ui/card';
import { FolderIcon } from '@/components/ui/icons';

export interface StitchExpenseBreakdownProps {
  items: CategoryBreakdownItem[];
  currency: string;
  isLoading: boolean;
  topN?: number | undefined;
}

const ROW_PALETTE = [colors.primary, colors.warning, colors.success, colors.danger, colors.text, colors.textMuted];

/**
 * Lista vertical de gastos por categoría con icono, label, importe,
 * porcentaje y barra de progreso. Top N + "Otros (k)" agrupa la cola.
 */
export function StitchExpenseBreakdown({
  items,
  currency,
  isLoading,
  topN = 5,
}: StitchExpenseBreakdownProps) {
  const sorted = [...items].sort((a, b) => Number(b.total) - Number(a.total));
  const total = sorted.reduce((acc, x) => acc + Number(x.total), 0);
  const top = sorted.slice(0, topN);
  const rest = sorted.slice(topN);
  const restTotal = rest.reduce((acc, x) => acc + Number(x.total), 0);
  const empty = !isLoading && total === 0;

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
          Desglose de gastos
        </h3>
        <span
          style={{
            fontSize: fontSize.xs,
            color: colors.textMuted,
          }}
        >
          {top.length + (rest.length > 0 ? 1 : 0)} categorías
        </span>
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          Sin gastos en el periodo.
        </p>
      ) : (
        <ul
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
          }}
        >
          {top.map((item, idx) => {
            const Icon = iconForCategoryName(item.category_name);
            const color = ROW_PALETTE[idx % ROW_PALETTE.length] ?? colors.primary;
            return (
              <Row
                key={item.category_id ?? `_no_cat_${item.category_name}`}
                Icon={Icon}
                label={item.category_name}
                value={Number(item.total)}
                total={total}
                color={color}
                currency={currency}
              />
            );
          })}
          {rest.length > 0 ? (
            <Row
              Icon={FolderIcon}
              label={`Otros (${rest.length})`}
              value={restTotal}
              total={total}
              color={colors.borderStrong}
              currency={currency}
              muted
            />
          ) : null}
        </ul>
      )}
    </Card>
  );
}

function Row({
  Icon,
  label,
  value,
  total,
  color,
  currency,
  muted = false,
}: {
  Icon: React.ComponentType<{ size?: number | undefined }>;
  label: string;
  value: number;
  total: number;
  color: string;
  currency: string;
  muted?: boolean;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <li style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
      <div
        aria-hidden
        style={{
          width: 40,
          height: 40,
          borderRadius: radius.sm,
          backgroundColor: colors.surfaceMuted,
          color: muted ? colors.textMuted : color,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: '0 0 auto',
          border: `1px solid ${colors.border}`,
        }}
      >
        <Icon size={20} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: spacing.sm,
            marginBottom: 4,
          }}
        >
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: muted ? colors.textMuted : colors.text,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {label}
          </span>
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: muted ? colors.textMuted : colors.text,
              fontVariantNumeric: 'tabular-nums',
              whiteSpace: 'nowrap',
            }}
          >
            {formatAmount(String(value.toFixed(2)), currency)} · {pct.toFixed(0)}%
          </span>
        </div>
        <div
          style={{
            width: '100%',
            height: 6,
            backgroundColor: colors.surfaceMuted,
            borderRadius: 3,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: '100%',
              backgroundColor: color,
              transition: 'width 200ms ease',
            }}
          />
        </div>
      </div>
    </li>
  );
}
