'use client';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from './button';

export interface PaginationProps {
  /** Total de elementos disponibles. */
  total: number;
  /** Offset actual (0-indexed). */
  offset: number;
  /** Tamaño de página. */
  limit: number;
  /** Cantidad de elementos en la página actual (`items.length`). */
  pageItemCount: number;
  /** Callback con el nuevo offset. */
  onChange: (offset: number) => void;
  /** Cuántas páginas numéricas mostrar como máximo (default 5). */
  maxButtons?: number | undefined;
  /** Texto a mostrar en la izquierda; ej. "Mostrando 1–20 de 128". */
  summaryLabel?: string | undefined;
}

/**
 * Paginación numérica con elipsis. Anterior/Siguiente como botones
 * `ghost`, páginas como pills compactas con activo en `primary` filled.
 *
 * Ejemplo de visualización con 8 páginas, en la 4 de 8:
 *   « 1 … 3 [4] 5 … 8 »
 */
export function Pagination({
  total,
  offset,
  limit,
  pageItemCount,
  onChange,
  maxButtons = 5,
  summaryLabel,
}: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / Math.max(limit, 1)));
  const currentPage = Math.floor(offset / Math.max(limit, 1)) + 1;
  const hasPrev = offset > 0;
  const hasNext = offset + pageItemCount < total;

  const pages = computePageWindow(currentPage, pageCount, maxButtons);
  const defaultSummary =
    pageItemCount > 0
      ? `Mostrando ${offset + 1}–${offset + pageItemCount} de ${total}`
      : '0';

  return (
    <footer
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        marginTop: spacing.lg,
        flexWrap: 'wrap',
      }}
    >
      <span style={{ color: colors.textMuted, fontSize: fontSize.sm }}>
        {summaryLabel ?? defaultSummary}
      </span>
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
        <Button
          variant="ghost"
          disabled={!hasPrev}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          ← Anterior
        </Button>
        {pages.map((p, i) =>
          p === '…' ? (
            <span
              key={`gap-${i}`}
              style={{ color: colors.textSubtle, padding: `0 ${spacing.xs}px` }}
            >
              …
            </span>
          ) : (
            <PageButton
              key={p}
              page={p}
              active={p === currentPage}
              onClick={() => onChange((p - 1) * limit)}
            />
          ),
        )}
        <Button
          variant="ghost"
          disabled={!hasNext}
          onClick={() => onChange(offset + limit)}
        >
          Siguiente →
        </Button>
      </div>
    </footer>
  );
}

function PageButton({
  page,
  active,
  onClick,
}: {
  page: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      style={{
        minWidth: 32,
        height: 32,
        padding: `0 ${spacing.sm}px`,
        backgroundColor: active ? colors.primary : 'transparent',
        color: active ? colors.onPrimary : colors.text,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: radius.md,
        cursor: 'pointer',
        fontSize: fontSize.sm,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        fontVariantNumeric: 'tabular-nums',
        transition: 'background-color 120ms ease, border-color 120ms ease',
      }}
    >
      {page}
    </button>
  );
}

/**
 * Genera la ventana de páginas a mostrar. Estrategia: la primera, la
 * última, las (maxButtons-2) cercanas a la actual, y elipsis donde
 * haga falta.
 */
function computePageWindow(
  current: number,
  total: number,
  maxButtons: number,
): (number | '…')[] {
  if (total <= maxButtons) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const innerSlots = maxButtons - 2; // dejar hueco para 1 y last
  const half = Math.floor(innerSlots / 2);
  let start = Math.max(2, current - half);
  let end = Math.min(total - 1, current + (innerSlots - 1 - half));

  // Reajusta si se va por el borde.
  if (current - half < 2) {
    end = Math.min(total - 1, end + (2 - (current - half)));
  }
  if (current + (innerSlots - 1 - half) > total - 1) {
    start = Math.max(2, start - (current + (innerSlots - 1 - half) - (total - 1)));
  }

  const pages: (number | '…')[] = [1];
  if (start > 2) pages.push('…');
  for (let p = start; p <= end; p++) pages.push(p);
  if (end < total - 1) pages.push('…');
  pages.push(total);
  return pages;
}
