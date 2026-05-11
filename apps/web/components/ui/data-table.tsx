'use client';

import type { CSSProperties, ReactNode } from 'react';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

export type DataTableAlign = 'left' | 'right' | 'center';

export interface DataTableColumn<T> {
  /** Identificador único de la columna. Sirve como `key` de React. */
  key: string;
  /** Cabecera. Se renderiza con tipografía `overline`. */
  header: ReactNode;
  /** Render por fila. */
  render: (row: T, index: number) => ReactNode;
  /** Alineación horizontal del contenido (afecta a header y celdas). */
  align?: DataTableAlign | undefined;
  /** Ancho fijo o min-width por columna; útil para fechas o importes. */
  width?: string | number | undefined;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  /** Función que devuelve la key estable de cada fila. */
  rowKey: (row: T, index: number) => string;
  /** Click en una fila — opcional. Si está, las filas son focusables. */
  onRowClick?: ((row: T, index: number) => void) | undefined;
  /** Mensaje cuando `rows.length === 0`. */
  emptyMessage?: string | undefined;
}

/**
 * Tabla de datos genérica. No incluye paginación ni filtros: el caller
 * los aporta encima/debajo. Estilo:
 *  - cabecera: overline (12 px semibold uppercase) sobre `surface-muted`
 *  - filas: hover `surface-muted`, divider `border` entre filas
 *  - radio `md` en el contenedor con borde 1 px hairline
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  emptyMessage = 'Sin datos.',
}: DataTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div
        style={{
          padding: spacing.lg,
          textAlign: 'center',
          color: colors.textMuted,
          fontSize: fontSize.sm,
          backgroundColor: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
        }}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: fontSize.sm,
        }}
      >
        <thead>
          <tr style={{ backgroundColor: colors.surfaceMuted }}>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  padding: `${spacing.sm}px ${spacing.md}px`,
                  textAlign: col.align ?? 'left',
                  width: col.width,
                  fontSize: fontSize.xs,
                  fontWeight: fontWeight.semibold,
                  color: colors.textMuted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  borderBottom: `1px solid ${colors.border}`,
                  whiteSpace: 'nowrap',
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <Row
              key={rowKey(row, idx)}
              row={row}
              index={idx}
              columns={columns}
              isLast={idx === rows.length - 1}
              onRowClick={onRowClick}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface RowProps<T> {
  row: T;
  index: number;
  columns: DataTableColumn<T>[];
  isLast: boolean;
  onRowClick: ((row: T, index: number) => void) | undefined;
}

function Row<T>({ row, index, columns, isLast, onRowClick }: RowProps<T>) {
  const clickable = onRowClick !== undefined;
  const baseStyle: CSSProperties = {
    cursor: clickable ? 'pointer' : 'default',
    transition: 'background-color 120ms ease',
  };

  function handleClick() {
    onRowClick?.(row, index);
  }
  function handleKeyDown(event: React.KeyboardEvent<HTMLTableRowElement>) {
    if (!clickable) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleClick();
    }
  }

  return (
    <tr
      onClick={clickable ? handleClick : undefined}
      onKeyDown={clickable ? handleKeyDown : undefined}
      tabIndex={clickable ? 0 : undefined}
      role={clickable ? 'button' : undefined}
      style={baseStyle}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = colors.surfaceMuted;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent';
      }}
    >
      {columns.map((col) => (
        <td
          key={col.key}
          style={{
            padding: `${spacing.sm + 2}px ${spacing.md}px`,
            textAlign: col.align ?? 'left',
            color: colors.text,
            borderBottom: isLast ? 'none' : `1px solid ${colors.border}`,
            verticalAlign: 'middle',
          }}
        >
          {col.render(row, index)}
        </td>
      ))}
    </tr>
  );
}
