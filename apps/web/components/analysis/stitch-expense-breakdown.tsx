'use client';

import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';

import type { AnalyticsCategoryAmount, CategoryBreakdownItem } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

import { iconForCategoryName } from '@/lib/category-icons';
import { Card } from '@/components/ui/card';
import { FolderIcon } from '@/components/ui/icons';

/** PHASE-37.3 — filtro estructural/puntual del desglose. */
export type StructureFilter = 'all' | 'structural' | 'exceptional';

export interface StitchExpenseBreakdownProps {
  items: CategoryBreakdownItem[];
  currency: string;
  isLoading: boolean;
  topN?: number | undefined;
  /**
   * PHASE-37.3 — gasto puntual por categoría. Cuando se pasa, se habilita
   * el control `[Todo | Estructural | Puntual]`: "Puntual" usa esta lista y
   * "Estructural" se deriva restándola del total por categoría.
   */
  exceptionalByCategory?: AnalyticsCategoryAmount[] | undefined;
}

const STRUCTURE_LABELS: Record<StructureFilter, string> = {
  all: 'Todo',
  structural: 'Estructural',
  exceptional: 'Puntual',
};

/** Clave de emparejamiento entre datasets: id real o el bucket sin categoría. */
function categoryKey(id: string | null): string {
  return id ?? '_nocat_';
}

function toBreakdownItem(c: AnalyticsCategoryAmount): CategoryBreakdownItem {
  return {
    category_id: c.category_id,
    category_name: c.category_name ?? 'Sin categoría',
    category_kind: 'expense',
    category_color: c.color,
    category_icon: c.icon,
    total: c.total,
    count: 0,
  };
}

/** Estructural por categoría = total − puntual (descarta lo que queda ~0). */
export function deriveStructural(
  all: CategoryBreakdownItem[],
  exceptional: AnalyticsCategoryAmount[],
): CategoryBreakdownItem[] {
  const excByKey = new Map<string, number>();
  for (const e of exceptional) excByKey.set(categoryKey(e.category_id), Number(e.total));
  const out: CategoryBreakdownItem[] = [];
  for (const it of all) {
    const structural = Number(it.total) - (excByKey.get(categoryKey(it.category_id)) ?? 0);
    if (structural > 0.005) out.push({ ...it, total: structural.toFixed(2) });
  }
  return out;
}

const SLICE_PALETTE = [
  colors.primary,
  colors.warning,
  colors.success,
  colors.danger,
  colors.text,
  colors.borderStrong,
];

interface Slice {
  id: string;
  label: string;
  value: number;
  color: string;
  emoji: string | null;
  pct: number;
  isOther: boolean;
  /** PHASE-25: id real de la categoría para enlazar al drill-down. */
  categoryId: string | null;
  /** PHASE-25: categorías agregadas dentro del "Otros" — null si no es Otros. */
  groupedItems: CategoryBreakdownItem[] | null;
}

/**
 * Donut de gastos por categoría — Recharts (PHASE-18.1). Top N + "Otros"
 * agrupado, leyenda lateral con icono + amount + porcentaje, centro con
 * el total. Hover resalta el slice y aumenta su radio.
 */
export function StitchExpenseBreakdown({
  items,
  currency,
  isLoading,
  // PHASE-37.2 — top-6 (antes 5): el "Otros" agrupaba demasiadas categorías
  // (la queja era "Otros (39%)"). La fila "Otros (n)" sigue siendo clicable
  // para desplegar la lista completa inline (`otherExpanded`).
  topN = 6,
  exceptionalByCategory,
}: StitchExpenseBreakdownProps) {
  const router = useRouter();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [otherExpanded, setOtherExpanded] = useState(false);
  const [filter, setFilter] = useState<StructureFilter>('all');

  const canFilter = exceptionalByCategory != null;
  const exceptionalItems = useMemo(
    () => (exceptionalByCategory ?? []).map(toBreakdownItem),
    [exceptionalByCategory],
  );
  const structuralItems = useMemo(
    () => deriveStructural(items, exceptionalByCategory ?? []),
    [items, exceptionalByCategory],
  );
  const displayItems =
    !canFilter || filter === 'all'
      ? items
      : filter === 'exceptional'
        ? exceptionalItems
        : structuralItems;

  const sorted = [...displayItems].sort((a, b) => Number(b.total) - Number(a.total));
  const total = sorted.reduce((acc, x) => acc + Number(x.total), 0);
  // Si el usuario ha desplegado "Otros", mostramos TODAS las categorías
  // y se omite el bucket agrupado. Si no, top N + Otros (PHASE-25).
  const top = otherExpanded ? sorted : sorted.slice(0, topN);
  const rest = otherExpanded ? [] : sorted.slice(topN);
  const restTotal = rest.reduce((acc, x) => acc + Number(x.total), 0);
  const empty = !isLoading && total === 0;

  const slices: Slice[] = [
    ...top.map((item, idx) => ({
      id: item.category_id ?? `_no_cat_${item.category_name}`,
      label: item.category_name,
      value: Number(item.total),
      color:
        item.category_color ??
        SLICE_PALETTE[idx % SLICE_PALETTE.length] ??
        colors.primary,
      emoji: item.category_icon,
      pct: total > 0 ? (Number(item.total) / total) * 100 : 0,
      isOther: false,
      categoryId: item.category_id,
      groupedItems: null,
    })),
  ];
  if (rest.length > 0) {
    slices.push({
      id: '_other',
      label: `Otros (${rest.length})`,
      value: restTotal,
      color: colors.borderStrong,
      emoji: null,
      pct: total > 0 ? (restTotal / total) * 100 : 0,
      isOther: true,
      categoryId: null,
      groupedItems: rest,
    });
  }

  function handleSliceClick(slice: Slice) {
    if (slice.isOther) {
      setOtherExpanded(true);
      return;
    }
    if (slice.categoryId) {
      router.push(`/personal-finance/analysis/category/${slice.categoryId}` as never);
    }
  }

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
        {canFilter ? (
          <StructureSegmented value={filter} onChange={setFilter} />
        ) : (
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {slices.length} {slices.length === 1 ? 'categoría' : 'categorías'}
          </span>
        )}
      </header>

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          {filter === 'exceptional'
            ? 'Sin gastos puntuales en el periodo.'
            : filter === 'structural'
              ? 'Sin gastos estructurales en el periodo.'
              : 'Sin gastos en el periodo.'}
        </p>
      ) : (
        <div
          style={{
            display: 'flex',
            gap: spacing.lg,
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ position: 'relative', width: 220, height: 220, flex: '0 0 auto' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  innerRadius={62}
                  outerRadius={92}
                  paddingAngle={2}
                  isAnimationActive
                  animationDuration={500}
                  onMouseEnter={(_, idx) => setActiveId(slices[idx]?.id ?? null)}
                  onMouseLeave={() => setActiveId(null)}
                  onClick={(_, idx) => {
                    const s = slices[idx];
                    if (s) handleSliceClick(s);
                  }}
                  cursor="pointer"
                  stroke={colors.surface}
                  strokeWidth={2}
                >
                  {slices.map((s) => (
                    <Cell
                      key={s.id}
                      fill={s.color}
                      fillOpacity={activeId === null || activeId === s.id ? 1 : 0.45}
                      style={{ transition: 'fill-opacity 120ms ease' }}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                pointerEvents: 'none',
                padding: spacing.sm,
                textAlign: 'center',
              }}
            >
              {/* PHASE-29.6: el centro reacciona al hover de un slice.
                  Sin slice activo → "Total · {amount}". Con uno →
                  "{label} · {value} · {pct}%". Transición opacidad
                  para evitar el salto duro. */}
              <DonutCenter
                activeSlice={
                  activeId ? slices.find((s) => s.id === activeId) ?? null : null
                }
                total={total}
                currency={currency}
              />
            </div>
          </div>

          <ul
            style={{
              flex: '1 1 220px',
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: spacing.sm,
            }}
          >
            {slices.map((s) => (
              <LegendRow
                key={s.id}
                slice={s}
                currency={currency}
                hovered={activeId === s.id}
                onHover={(hovered) => setActiveId(hovered ? s.id : null)}
                onClick={() => handleSliceClick(s)}
              />
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

/** Control segmentado [Todo | Estructural | Puntual] (PHASE-37.3). */
export function StructureSegmented({
  value,
  onChange,
}: {
  value: StructureFilter;
  onChange: (next: StructureFilter) => void;
}) {
  const options: StructureFilter[] = ['all', 'structural', 'exceptional'];
  return (
    <div
      role="tablist"
      aria-label="Filtrar gasto por tipo"
      style={{
        display: 'inline-flex',
        gap: 2,
        padding: 2,
        borderRadius: radius.sm,
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
      }}
    >
      {options.map((opt) => {
        const active = value === opt;
        return (
          <button
            key={opt}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt)}
            style={{
              padding: '4px 10px',
              borderRadius: radius.sm - 2,
              border: 'none',
              cursor: 'pointer',
              fontSize: fontSize.xs,
              fontWeight: active ? fontWeight.semibold : fontWeight.medium,
              backgroundColor: active ? colors.surface : 'transparent',
              color: active ? colors.text : colors.textMuted,
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.18)' : 'none',
              transition: 'background-color 120ms ease, color 120ms ease',
            }}
          >
            {STRUCTURE_LABELS[opt]}
          </button>
        );
      })}
    </div>
  );
}

function DonutCenter({
  activeSlice,
  total,
  currency,
}: {
  activeSlice: Slice | null;
  total: number;
  currency: string;
}) {
  const showSlice = activeSlice !== null;
  return (
    <>
      <span
        style={{
          fontSize: fontSize.xs,
          color: showSlice ? activeSlice.color : colors.textMuted,
          fontWeight: showSlice ? fontWeight.semibold : fontWeight.medium,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: '88%',
          transition: 'color 120ms ease, opacity 120ms ease',
        }}
      >
        {showSlice ? activeSlice.label : 'Total'}
      </span>
      <span
        style={{
          fontSize: fontSize.lg,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          fontVariantNumeric: 'tabular-nums',
          marginTop: 2,
        }}
      >
        {formatAmount(
          String((showSlice ? activeSlice.value : total).toFixed(2)),
          currency,
        )}
      </span>
      {showSlice ? (
        <span
          style={{
            fontSize: 11,
            color: colors.textMuted,
            fontVariantNumeric: 'tabular-nums',
            marginTop: 2,
          }}
        >
          {activeSlice.pct.toFixed(0)}% del total
        </span>
      ) : null}
    </>
  );
}

function LegendRow({
  slice,
  currency,
  hovered,
  onHover,
  onClick,
}: {
  slice: Slice;
  currency: string;
  hovered: boolean;
  onHover: (next: boolean) => void;
  onClick: () => void;
}) {
  const Icon = slice.isOther ? FolderIcon : iconForCategoryName(slice.label);
  const clickable = slice.isOther || slice.categoryId != null;
  return (
    <li
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onClick={clickable ? onClick : undefined}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `${spacing.xs}px ${spacing.sm}px`,
        borderRadius: radius.sm,
        backgroundColor: hovered ? colors.surfaceMuted : 'transparent',
        transition: 'background-color 120ms ease',
        cursor: clickable ? 'pointer' : 'default',
      }}
      title={
        slice.isOther
          ? 'Expandir las categorías agrupadas'
          : slice.categoryId
            ? 'Ver desglose de esta categoría'
            : undefined
      }
    >
      <span
        aria-hidden
        style={{
          width: 32,
          height: 32,
          borderRadius: radius.sm,
          backgroundColor: colors.surfaceMuted,
          color: slice.isOther ? colors.textMuted : slice.color,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: '0 0 auto',
          border: `1px solid ${colors.border}`,
        }}
      >
        {slice.emoji ? (
          <span style={{ fontSize: fontSize.md, lineHeight: 1 }}>{slice.emoji}</span>
        ) : (
          <Icon size={16} />
        )}
      </span>
      <span
        style={{
          flex: 1,
          minWidth: 0,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.medium,
          color: slice.isOther ? colors.textMuted : colors.text,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {slice.label}
      </span>
      <span
        style={{
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: slice.isOther ? colors.textMuted : colors.text,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatAmount(String(slice.value.toFixed(2)), currency)}
      </span>
      <span
        style={{
          fontSize: 11,
          color: colors.textMuted,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
          minWidth: 36,
          textAlign: 'right',
        }}
      >
        {slice.pct.toFixed(0)}%
      </span>
    </li>
  );
}

