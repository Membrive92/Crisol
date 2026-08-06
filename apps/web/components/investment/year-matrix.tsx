'use client';

import type { CSSProperties, ReactNode } from 'react';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

export interface MatrixCell {
  /** Texto ya formateado. `—` para hueco. */
  text: string;
  /** Color del texto (el semáforo lo decide quien construye la fila). */
  color?: string | undefined;
  /** Fondo suave de banda. */
  background?: string | undefined;
  /** Explicación al pasar por encima (razón de un no-calculable, el corte…). */
  title?: string | undefined;
  /** Marca de aproximación / procedencia degradada. */
  mark?: string | undefined;
}

export interface MatrixRow {
  key: string;
  label: string;
  /** Nota bajo la etiqueta: el corte aplicado, o por qué no se pudo calcular. */
  hint?: string | undefined;
  /** Sub-cabecera de bloque (Activo corriente, Solvencia…). No lleva celdas. */
  isGroup?: boolean | undefined;
  /** Fila de total: se resalta. */
  emphasis?: boolean | undefined;
  cells: MatrixCell[];
}

export interface YearMatrixProps {
  years: number[];
  rows: MatrixRow[];
  /** Ejercicio que alimenta el dictamen: se marca con • en la cabecera. */
  verdictYear?: number | undefined;
  /** Cabecera de la primera columna. */
  firstColumnLabel?: string;
  /** Leyenda bajo la tabla (símbolos usados). */
  legend?: ReactNode;
}

/**
 * Matriz concepto × ejercicio: una fila por concepto, una columna por año.
 *
 * Es la forma en la que el usuario lee su cuaderno («una columna por año,
 * 2016-2020»), y la que el informe no tenía: hasta PHASE-44.9 todo se congelaba
 * en el último ejercicio pese a que el motor calcula y guarda **todos** los años
 * con su banda.
 *
 * La tabla scrollea DENTRO de su contenedor; la página nunca hace scroll
 * horizontal. La primera columna queda fija para no perder de vista el concepto.
 */
export function YearMatrix({
  years,
  rows,
  verdictYear,
  firstColumnLabel = 'Concepto',
  legend,
}: YearMatrixProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: fontSize.sm,
            minWidth: 320,
          }}
        >
          <thead>
            <tr>
              <th style={headerCellStyle(true)}>{firstColumnLabel}</th>
              {years.map((year) => (
                <th key={year} style={headerCellStyle(false)}>
                  {year}
                  {year === verdictYear ? (
                    <span title="Ejercicio que alimenta el dictamen"> •</span>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) =>
              row.isGroup ? (
                <tr key={row.key}>
                  <th colSpan={years.length + 1} scope="colgroup" style={groupRowStyle}>
                    {row.label}
                  </th>
                </tr>
              ) : (
                <tr key={row.key}>
                  <th scope="row" style={labelCellStyle(row.emphasis)}>
                    <span>{row.label}</span>
                    {row.hint ? (
                      <span
                        style={{
                          display: 'block',
                          color: colors.textSubtle,
                          fontSize: fontSize.xs,
                          fontWeight: fontWeight.regular,
                          marginTop: 2,
                        }}
                      >
                        {row.hint}
                      </span>
                    ) : null}
                  </th>
                  {row.cells.map((cell, index) => (
                    <td
                      key={`${row.key}-${years[index] ?? index}`}
                      title={cell.title}
                      style={valueCellStyle(cell, row.emphasis)}
                    >
                      {cell.text}
                      {cell.mark ? (
                        <span style={{ color: colors.textSubtle }}>{cell.mark}</span>
                      ) : null}
                    </td>
                  ))}
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
      {legend ? (
        <div style={{ color: colors.textSubtle, fontSize: fontSize.xs, lineHeight: 1.6 }}>
          {legend}
        </div>
      ) : null}
    </div>
  );
}

function headerCellStyle(first: boolean): CSSProperties {
  return {
    textAlign: first ? 'left' : 'right',
    padding: `${spacing.xs}px ${spacing.sm}px`,
    borderBottom: `1px solid ${colors.border}`,
    color: colors.textMuted,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    whiteSpace: 'nowrap',
    position: first ? 'sticky' : undefined,
    left: first ? 0 : undefined,
    backgroundColor: colors.surface,
    zIndex: first ? 1 : undefined,
  };
}

const groupRowStyle: CSSProperties = {
  textAlign: 'left',
  padding: `${spacing.md}px ${spacing.sm}px ${spacing.xs}px`,
  color: colors.textMuted,
  fontSize: fontSize.xs,
  fontWeight: fontWeight.bold,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

function labelCellStyle(emphasis: boolean | undefined): CSSProperties {
  return {
    textAlign: 'left',
    padding: `${spacing.xs}px ${spacing.sm}px`,
    borderBottom: `1px solid ${colors.border}`,
    color: emphasis ? colors.text : colors.textMuted,
    fontSize: fontSize.sm,
    fontWeight: emphasis ? fontWeight.semibold : fontWeight.regular,
    position: 'sticky',
    left: 0,
    backgroundColor: colors.surface,
    minWidth: 180,
    maxWidth: 320,
  };
}

function valueCellStyle(cell: MatrixCell, emphasis: boolean | undefined): CSSProperties {
  return {
    textAlign: 'right',
    padding: `${spacing.xs}px ${spacing.sm}px`,
    borderBottom: `1px solid ${colors.border}`,
    backgroundColor: cell.background,
    color: cell.color ?? colors.text,
    fontWeight: emphasis ? fontWeight.semibold : fontWeight.regular,
    fontVariantNumeric: 'tabular-nums',
    whiteSpace: 'nowrap',
  };
}
