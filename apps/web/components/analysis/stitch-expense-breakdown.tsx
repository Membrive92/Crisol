'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';

import type {
  AnalyticsCategoryAmount,
  CategoryBreakdownItem,
  CategoryStructureExplain,
  StructureReason,
} from '@crisol/types';
import {
  colors,
  deferredBreakdownNotice,
  deriveStructural,
  deferredCategoryNotice,
  deferredInView,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
  toBreakdownRow,
} from '@crisol/ui';

import { iconForCategoryName } from '@/lib/category-icons';
import { Card } from '@/components/ui/card';
import { FolderIcon } from '@/components/ui/icons';

/** PHASE-37.3 — filtro estructural/puntual del desglose. */
export type StructureFilter = 'all' | 'structural' | 'exceptional';

export interface StitchExpenseBreakdownProps {
  items: CategoryBreakdownItem[];
  currency: string;
  isLoading: boolean;
  /**
   * Rango del periodo activo (ISO). Se propaga al drill-down de categoría vía
   * query `?from&to` para que el detalle herede el MISMO periodo (mes/trimestre)
   * en vez de caer a su default anual.
   */
  dateFrom?: string | undefined;
  dateTo?: string | undefined;
  /**
   * PHASE-37.3 — gasto puntual por categoría. Cuando se pasa, se habilita
   * el control `[Todo | Fijo | Variable]`: "Variable" (excepcional) usa esta
   * lista y "Fijo" (estructural) se deriva restándola del total por categoría.
   */
  exceptionalByCategory?: AnalyticsCategoryAmount[] | undefined;
  /**
   * PHASE-41 — filtro controlado desde la página (para persistirlo en la URL).
   * Si no se pasa, el componente lo gestiona internamente (default `all`).
   */
  filter?: StructureFilter | undefined;
  onFilterChange?: ((next: StructureFilter) => void) | undefined;
  /**
   * PHASE-41 — query string del estado de Análisis (`period&anchor&filter`).
   * Se adjunta como `?back=` al drill-down para que el detalle de categoría
   * pueda volver restaurando el mismo período/filtro.
   */
  backQuery?: string | undefined;
  /**
   * PHASE-43.2 — explicabilidad por categoría (endpoint explain). Cuando se
   * pasa, cada fila de la leyenda muestra en su tooltip POR QUÉ es fija o
   * variable. Opcional: sin ella el desglose funciona igual.
   */
  explain?: CategoryStructureExplain[] | undefined;
  /**
   * PHASE-47.E2 — cuánto del gasto de este periodo está APLAZADO por un recibo
   * financiado. Estas compras SÍ están en el desglose (el gasto se hizo) pero
   * NO en el resultado del mes (el dinero no salió), así que las dos cifras no
   * cuadran a propósito. Se pinta el aviso para que quien lo intente sepa por
   * qué, en vez de concluir que la app está mal.
   */
  deferredExpenses?: string | null | undefined;
}

const STRUCTURE_LABELS: Record<StructureFilter, string> = {
  all: 'Todo',
  structural: 'Fijo',
  exceptional: 'Variable',
};

const REASON_LABELS: Record<StructureReason, string> = {
  override_category: 'marcada manualmente',
  rule_1_fixed_expense: 'tiene un gasto fijo confirmado',
  rule_2_debt_role: 'es pago de deuda',
  rule_3_recurrence: 'recurre con importe estable',
  not_recurring: 'no recurre de forma estable',
  insufficient_history: 'sin histórico suficiente',
};

/** Texto del tooltip: "Fijo · recurre con importe estable (5 de 6 meses)". */
function explainTooltip(e: CategoryStructureExplain): string {
  const head = e.is_structural ? 'Fijo' : 'Variable';
  const reason = REASON_LABELS[e.reason];
  const showMonths =
    e.reason === 'rule_3_recurrence' ||
    e.reason === 'not_recurring' ||
    e.reason === 'insufficient_history';
  const detail = showMonths ? ` (${e.months_in_band} de ${e.months_active} meses en banda)` : '';
  return `${head} · ${reason}${detail}`;
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
  /**
   * PHASE-47.E4: la parte de `value` que quedó aplazada, o `null` si el
   * backend no lo declara. `null` ≠ `'0'`: el primero es «no se sabe» y el
   * segundo «no hay nada aplazado aquí».
   */
  deferred: string | null;
  /**
   * Id del slice del DONUT al que pertenece esta entrada de la leyenda: su
   * propio id si está en el top-N, o `'_other'` si cae en la cola agrupada.
   * Sincroniza el hover leyenda↔donut cuando ambos están desacoplados (la
   * leyenda lista todas las categorías, el donut agrupa la cola).
   */
  donutId: string;
}

/**
 * Donut de gastos por categoría — Recharts (PHASE-18.1). Donut y LEYENDA
 * muestran el MISMO conjunto: TODAS las categorías individualmente (sin agrupar
 * en "Otros", que confundía al aparecer en el donut pero no en la lista). La
 * leyenda las reparte en columnas para llenar la card. Centro con el total; el
 * hover sincroniza donut↔fila 1:1 vía `donutId`.
 */
export function StitchExpenseBreakdown({
  items,
  currency,
  isLoading,
  exceptionalByCategory,
  dateFrom,
  dateTo,
  filter: filterProp,
  onFilterChange,
  backQuery,
  explain,
  deferredExpenses,
}: StitchExpenseBreakdownProps) {
  const router = useRouter();
  const explainById = useMemo(() => {
    const map = new Map<string, CategoryStructureExplain>();
    for (const e of explain ?? []) map.set(e.category_id, e);
    return map;
  }, [explain]);
  // `activeId` = slice del DONUT resaltado (dim del donut + centro).
  // `hoveredLegendId` = fila CONCRETA de la leyenda bajo el cursor. Se separan
  // porque las categorías de la cola comparten `donutId='_other'`: si el
  // resaltado de la fila usara `donutId`, pasar por una encendería todas.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hoveredLegendId, setHoveredLegendId] = useState<string | null>(null);
  // PHASE-41 — filtro controlado por la página cuando llega `filterProp`
  // (para persistirlo en la URL); si no, estado interno.
  const [internalFilter, setInternalFilter] = useState<StructureFilter>('all');
  const filter = filterProp ?? internalFilter;
  const setFilter = onFilterChange ?? setInternalFilter;
  // PHASE-47.E2 — la diferencia entre este desglose y el resultado del mes,
  // dicha en voz alta. La redacción vive en `@crisol/ui` para que móvil no
  // acabe explicándolo con otras palabras.
  // Nota: el aviso se calcula MÁS ABAJO, a partir de `sorted` — las filas que
  // de verdad se están pintando. Ver `deferredEnVista`.
  // Paginación SÓLO de la leyenda (el donut nunca se pagina).
  const [page, setPage] = useState(0);
  // Al cambiar de filtro cambia el nº de categorías → a la primera página para
  // no quedar en una página inexistente.
  useEffect(() => {
    setPage(0);
  }, [filter]);

  const canFilter = exceptionalByCategory != null;
  const exceptionalItems = useMemo(
    () => (exceptionalByCategory ?? []).map(toBreakdownRow),
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
  const empty = !isLoading && total === 0;

  // PHASE-47.E2/E4 — la diferencia entre este desglose y el resultado del mes,
  // dicha en voz alta. La redacción vive en `@crisol/ui` para que móvil no
  // acabe explicándolo con otras palabras.
  //
  // El importe sale de las filas que se están MOSTRANDO, no del total del
  // periodo: bajo el filtro Fijo el aviso decía «496,67 € aplazados» cuando en
  // pantalla sólo había 245,53 € de ellos (los otros viven en categorías
  // variables). Si el backend no manda el dato por categoría, `deferredInView`
  // devuelve `null` y se cae al total del periodo — correcto sin filtro, y lo
  // único que se sabe.
  const deferredEnVista = deferredInView(sorted);
  const deferredNotice = deferredBreakdownNotice(
    deferredEnVista ?? (filter === 'all' ? deferredExpenses : null),
    currency,
  );

  const sliceId = (item: CategoryBreakdownItem): string =>
    item.category_id ?? `_no_cat_${item.category_name}`;
  const sliceColor = (item: CategoryBreakdownItem, idx: number): string =>
    item.category_color ?? SLICE_PALETTE[idx % SLICE_PALETTE.length] ?? colors.primary;

  // TODAS las categorías individualmente, MISMO conjunto en donut y leyenda
  // (coherentes: si la leyenda las lista todas, el donut también, sin un "Otros"
  // que luego no aparezca en la lista). `donutId` = id propio → el hover
  // sincroniza donut↔fila 1:1.
  const allSlices: Slice[] = sorted.map((item, idx) => ({
    id: sliceId(item),
    label: item.category_name,
    value: Number(item.total),
    color: sliceColor(item, idx),
    emoji: item.category_icon,
    pct: total > 0 ? (Number(item.total) / total) * 100 : 0,
    isOther: false,
    categoryId: item.category_id,
    groupedItems: null,
    donutId: sliceId(item),
    deferred: item.deferred_total ?? null,
  }));
  const donutSlices = allSlices;
  const legendItems = allSlices;

  // Paginación SÓLO de la leyenda (el donut nunca se pagina). Umbral alto: con
  // la card ancha casi todos ven todas sus categorías de una vez; el pager es el
  // fallback para catálogos enormes (>40).
  const LEGEND_PAGE_SIZE = 40;
  const pageCount = Math.max(1, Math.ceil(legendItems.length / LEGEND_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const legendSlices =
    pageCount > 1
      ? legendItems.slice(currentPage * LEGEND_PAGE_SIZE, (currentPage + 1) * LEGEND_PAGE_SIZE)
      : legendItems;

  function handleSliceClick(slice: Slice) {
    // La porción "Otros" del donut ya no expande nada: la leyenda lista todas
    // las categorías individualmente, así que no hay lista oculta que desplegar.
    if (slice.isOther) return;
    if (slice.categoryId) {
      // Propaga el periodo activo para que el drill-down herede el mismo
      // rango (mes/trimestre/año) en vez de su default anual.
      const params = new URLSearchParams();
      if (dateFrom) params.set('from', dateFrom);
      if (dateTo) params.set('to', dateTo);
      // PHASE-41 — arrastra el estado de Análisis para que "← Análisis" lo
      // restaure (período + filtro estructural/variable).
      if (backQuery) params.set('back', backQuery);
      const qs = params.toString();
      router.push(
        `/personal-finance/analysis/category/${slice.categoryId}${qs ? `?${qs}` : ''}` as never,
      );
    }
  }

  return (
    <Card style={{ padding: spacing.lg, display: 'flex', flexDirection: 'column' }}>
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
            {sorted.length} {sorted.length === 1 ? 'categoría' : 'categorías'}
          </span>
        )}
      </header>

      {deferredNotice ? (
        <p
          data-testid="deferred-notice"
          style={{
            margin: `0 0 ${spacing.md} 0`,
            fontSize: fontSize.xs,
            color: colors.textMuted,
            lineHeight: 1.5,
          }}
        >
          {deferredNotice}
        </p>
      ) : null}

      {empty ? (
        <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted }}>
          {filter === 'exceptional'
            ? 'Sin gastos variables en el periodo.'
            : filter === 'structural'
              ? 'Sin gastos fijos en el periodo.'
              : 'Sin gastos en el periodo.'}
        </p>
      ) : (
        <div
          style={{
            // Masonry: el cuerpo (donut + leyenda) toma su altura de contenido,
            // top-aligned. La card ya no se estira a la de deuda.
            display: 'flex',
            gap: spacing.lg,
            alignItems: 'flex-start',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              position: 'relative',
              width: 220,
              height: 220,
              flex: '0 0 auto',
            }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={donutSlices}
                  dataKey="value"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  innerRadius={62}
                  outerRadius={92}
                  // Sin paddingAngle: con muchas porciones las minúsculas serían
                  // más pequeñas que el padding y Recharts dejaría huecos (el
                  // donut "no cerraba"). `minAngle` garantiza que TODA categoría
                  // no-cero pinte un mínimo visible (el tooltip mantiene el valor
                  // real); así ninguna se queda sin dibujar. Separación por el
                  // `stroke` fino de 1px.
                  paddingAngle={0}
                  minAngle={3}
                  isAnimationActive
                  animationDuration={500}
                  onMouseEnter={(_, idx) => setActiveId(donutSlices[idx]?.id ?? null)}
                  onMouseLeave={() => setActiveId(null)}
                  onClick={(_, idx) => {
                    const s = donutSlices[idx];
                    if (s) handleSliceClick(s);
                  }}
                  cursor="pointer"
                  stroke={colors.surface}
                  strokeWidth={1}
                >
                  {donutSlices.map((s) => (
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
                activeSlice={activeId ? (donutSlices.find((s) => s.id === activeId) ?? null) : null}
                total={total}
                currency={currency}
              />
            </div>
          </div>

          <div style={{ flex: '1 1 320px', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                // Multi-columna: fluye las categorías en 1-3 columnas según el
                // ancho disponible (aprovecha el espacio en vez de una única
                // columna larguísima).
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                columnGap: spacing.md,
                // Espaciado cómodo y fijo entre filas; la lista toma su altura de
                // contenido (masonry) — sin repartir sobre un alto forzado.
                rowGap: spacing.md,
              }}
            >
              {legendSlices.map((s) => (
                <LegendRow
                  key={s.id}
                  slice={s}
                  currency={currency}
                  explain={s.categoryId ? explainById.get(s.categoryId) : undefined}
                  // Resaltado por `donutId`: al pasar por una fila de la cola se
                  // resalta la porción "Otros" del donut (y todas sus hermanas);
                  // al pasar por el donut, la porción resalta sus filas.
                  hovered={hoveredLegendId === s.id}
                  onHover={(hovered) => {
                    setHoveredLegendId(hovered ? s.id : null);
                    setActiveId(hovered ? s.donutId : null);
                  }}
                  onClick={() => handleSliceClick(s)}
                />
              ))}
            </ul>
            {pageCount > 1 ? (
              <LegendPager
                page={currentPage}
                pageCount={pageCount}
                onPage={(next) => setPage(next)}
              />
            ) : null}
          </div>
        </div>
      )}
    </Card>
  );
}

/** Pager de la leyenda (client-side). No afecta al donut. */
function LegendPager({
  page,
  pageCount,
  onPage,
}: {
  page: number;
  pageCount: number;
  onPage: (next: number) => void;
}) {
  const btnStyle = (disabled: boolean) => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 28,
    height: 28,
    borderRadius: radius.sm,
    border: `1px solid ${colors.border}`,
    backgroundColor: colors.surface,
    color: disabled ? colors.textSubtle : colors.text,
    cursor: disabled ? 'default' : 'pointer',
    fontSize: fontSize.md,
    lineHeight: 1,
  });
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing.sm,
        marginTop: spacing.md,
      }}
    >
      <button
        type="button"
        aria-label="Página anterior"
        disabled={page === 0}
        onClick={() => onPage(Math.max(0, page - 1))}
        style={btnStyle(page === 0)}
      >
        ‹
      </button>
      <span
        style={{
          fontSize: fontSize.xs,
          color: colors.textMuted,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        Página {page + 1} de {pageCount}
      </span>
      <button
        type="button"
        aria-label="Página siguiente"
        disabled={page >= pageCount - 1}
        onClick={() => onPage(Math.min(pageCount - 1, page + 1))}
        style={btnStyle(page >= pageCount - 1)}
      >
        ›
      </button>
    </div>
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
        {formatAmount(String((showSlice ? activeSlice.value : total).toFixed(2)), currency)}
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
  explain,
  hovered,
  onHover,
  onClick,
}: {
  slice: Slice;
  currency: string;
  explain?: CategoryStructureExplain | undefined;
  hovered: boolean;
  onHover: (next: boolean) => void;
  onClick: () => void;
}) {
  const Icon = slice.isOther ? FolderIcon : iconForCategoryName(slice.label);
  const clickable = slice.isOther || slice.categoryId != null;
  // PHASE-43.2 — el tooltip explica por qué es fija/variable si hay datos;
  // si no, cae al texto de acción por defecto ("ver desglose").
  const tooltip = explain
    ? explainTooltip(explain)
    : slice.isOther
      ? 'Expandir las categorías agrupadas'
      : slice.categoryId
        ? 'Ver desglose de esta categoría'
        : undefined;
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
      title={tooltip}
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
          // Sin truncado: si el nombre no cabe, envuelve en 2 líneas en vez de
          // cortarse con "…" (preferencia del usuario: paginar/envolver >
          // truncar). `overflowWrap` parte palabras muy largas si hace falta.
          lineHeight: 1.25,
          overflowWrap: 'anywhere',
        }}
      >
        {slice.label}
      </span>
      {/* PHASE-47.E4 — el asterisco que ya marca cada compra aplazada en la
          lista de transacciones, aquí a nivel de categoría: el aviso de arriba
          decía CUÁNTO hay aplazado pero no DÓNDE. Comprobación por VERDAD y
          contra cero, no `!== null`: `null` es «el backend no lo manda» y `0`
          es «esta categoría no tiene nada aplazado» — ninguno de los dos se
          marca. */}
      {slice.deferred && Number(slice.deferred) > 0 ? (
        <abbr
          data-testid="deferred-category-mark"
          title={deferredCategoryNotice(slice.deferred, currency)}
          style={{
            color: colors.primary,
            fontWeight: fontWeight.semibold,
            cursor: 'help',
            textDecoration: 'none',
            flex: '0 0 auto',
          }}
        >
          *
        </abbr>
      ) : null}
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
