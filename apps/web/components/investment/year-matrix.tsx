'use client';

import type { CSSProperties, ReactNode } from 'react';

import { colors, fontSize, fontWeight, helpParagraphs, MARK, spacing } from '@crisol/ui';
import { useEffect, useRef, useState } from 'react';

import type { MarkEntry, MatrixCell, MatrixRow, Sparkline } from '@crisol/ui';

import { HelpButton, helpTextStyle } from './help-toggle';

// El modelo de fila se comparte con móvil desde PHASE-44.8 (`@crisol/ui`); aquí
// queda sólo el renderizador HTML. Se re-exporta para no tocar los seis
// consumidores, que lo importan de este módulo desde 44.9.
export type { MatrixCell, MatrixRow };

export interface YearMatrixProps {
  years: number[];
  rows: MatrixRow[];
  /** Ejercicio que alimenta el dictamen: se marca con • en la cabecera. */
  verdictYear?: number | undefined;
  /** Cabecera de la primera columna. */
  firstColumnLabel?: string;
  /** Leyenda bajo la tabla (símbolos usados). */
  legend?: ReactNode;
  /**
   * Qué significa cada marca de una celda (PHASE-44.24.E).
   *
   * Separada de `legend` porque son cosas distintas: `legend` es prosa propia
   * de la pestaña, y esto se DERIVA del registro de marcas. Antes sólo dos de
   * las cinco pestañas de matriz explicaban sus marcas, así que en las otras
   * tres un `†` o un `≈` eran ruido tipográfico.
   */
  marksLegend?: readonly MarkEntry[] | undefined;
  /**
   * Fila a la que se ha llegado desde el veredicto (PHASE-44.24.C.4): se
   * resalta y se hace scroll hasta ella. El efecto vive AQUÍ y no en el origen
   * porque `TabPanel` desmonta las pestañas inactivas: cuando se pulsa el
   * enlace, esta tabla todavía no existe.
   */
  highlightKey?: string | undefined;
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
  marksLegend,
  highlightKey,
}: YearMatrixProps) {
  // PHASE-44.23 — una sola definición abierta a la vez. Con 49 partidas en la
  // pantalla de Estados, permitir varias convierte la tabla en un muro de
  // texto y se pierde justo lo que se venía a comparar: los números.
  const [openHelp, setOpenHelp] = useState<string | null>(null);
  // La columna existe si ALGUNA fila la tiene. Se decide aquí y no por fila
  // porque las cabeceras y los `colSpan` tienen que cuadrar con ella
  // (PHASE-44.24.D).
  const hasTrend = rows.some((row) => 'spark' in row);
  const span = years.length + 1 + (hasTrend ? 1 : 0);
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
                    <span title={MARK.verdict_year.title}> {MARK.verdict_year.glyph}</span>
                  ) : null}
                </th>
              ))}
              {hasTrend ? <th style={headerCellStyle(false)}>Tendencia</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) =>
              row.isGroup ? (
                <tr key={row.key}>
                  <th colSpan={span} scope="colgroup" style={groupRowStyle}>
                    {row.label}
                  </th>
                </tr>
              ) : (
                <MatrixDataRow
                  key={row.key}
                  row={row}
                  years={years}
                  highlighted={highlightKey === row.key}
                  open={openHelp === row.key}
                  hasTrend={hasTrend}
                  onToggleHelp={() =>
                    setOpenHelp((current) => (current === row.key ? null : row.key))
                  }
                />
              ),
            )}
          </tbody>
        </table>
      </div>
      {legend || marksLegend?.length ? (
        <div style={{ color: colors.textSubtle, fontSize: fontSize.xs, lineHeight: 1.6 }}>
          {legend}
          {marksLegend?.map((entry) => (
            <div key={entry.glyph}>
              <strong>{entry.glyph}</strong> {entry.title}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Una fila de datos, con su «i» de definición.
 *
 * PHASE-44.23 — la definición se despliega DEBAJO de la fila en vez de flotar
 * en un tooltip. Tres razones, y ninguna es estética: la tabla vive dentro de
 * un contenedor con `overflow-x: auto`, así que un flotante se recorta por el
 * borde; un `title=` no lo abre el teclado ni existe en táctil (la lección de
 * PHASE-44.15, que ya obligó a sacar un motivo de un `title` en el buscador); y
 * un texto de tres frases no cabe en un tooltip sin taparlo todo.
 *
 * El `title` se pone IGUALMENTE en el botón: para quien va con ratón, leerlo al
 * pasar por encima es más rápido que pulsar.
 */
function MatrixDataRow({
  row,
  years,
  open,
  onToggleHelp,
  highlighted = false,
  hasTrend = false,
}: {
  row: MatrixRow;
  years: number[];
  open: boolean;
  onToggleHelp: () => void;
  highlighted?: boolean;
  hasTrend?: boolean;
}) {
  const help = row.help;
  const ref = useRef<HTMLTableRowElement | null>(null);

  // Al llegar desde el veredicto, la fila se busca sola. El efecto corre al
  // montarse la pestaña de destino, que es cuando la fila existe por primera
  // vez — desde el origen no se podía, porque el panel estaba desmontado.
  useEffect(() => {
    // `?.` sobre el MÉTODO y no sólo sobre el nodo: jsdom no implementa
    // `scrollIntoView`, así que sin esta guarda el resaltado funcionaría en el
    // navegador y reventaría en los tests — la misma familia que `Blob.text()`
    // en PHASE-4.2. El scroll es una comodidad; el resaltado es lo que importa.
    if (highlighted) ref.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  }, [highlighted]);

  return (
    <>
      <tr
        ref={ref}
        {...(highlighted ? { 'aria-current': 'true' as const } : {})}
        style={highlighted ? { outline: `2px solid ${colors.primary}` } : undefined}
      >
        <th scope="row" style={labelCellStyle(row.emphasis)}>
          <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4 }}>
            <span>{row.label}</span>
            {help ? (
              <HelpButton label={row.label} help={help} open={open} onToggle={onToggleHelp} />
            ) : null}
          </span>
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
            {cell.mark ? <span style={{ color: colors.textSubtle }}>{cell.mark}</span> : null}
          </td>
        ))}
        {/* La celda se pinta VACÍA en las filas que no tienen serie —una
            comprobación del DuPont, una métrica que el motor no emitía— para
            que las columnas no se desalineen. */}
        {hasTrend ? (
          <td style={{ ...valueCellStyle({ text: '' }, row.emphasis), textAlign: 'center' }}>
            {'spark' in row ? <TrendCell spark={row.spark} /> : null}
          </td>
        ) : null}
      </tr>
      {open && help ? (
        <tr>
          <td colSpan={years.length + 1 + (hasTrend ? 1 : 0)} style={helpTextStyle}>
            {/* Los tramos en líneas separadas y no en un párrafo: «qué mide» se
                lee siempre, «por qué importa» una vez, y «cómo se lee» es lo
                que se vuelve a consultar. El orden y los rótulos vienen de
                `@crisol/ui` para que móvil diga exactamente lo mismo. */}
            {helpParagraphs(row).map((part, i) => (
              <p key={part.label ?? 'what'} style={{ margin: i === 0 ? 0 : '6px 0 0' }}>
                {part.label ? <strong style={{ color: colors.text }}>{part.label}: </strong> : null}
                {part.text}
              </p>
            ))}
          </td>
        </tr>
      ) : null}
    </>
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
    borderRight: first ? `1px solid ${colors.border}` : undefined,
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
    // El borde derecho es el límite visible de la columna fija: sin él, los
    // números se deslizaban por debajo de la etiqueta al hacer scroll sin que
    // nada dijera dónde acababa una y empezaban los otros.
    borderRight: `1px solid ${colors.border}`,
    minWidth: 132,
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

/**
 * La serie de una fila en un dibujo de 40×14 (PHASE-44.24.D).
 *
 * SVG a mano y no una librería: son cuatro puntos y una polilínea, y así el
 * `aria-label` lleva la frase que `@crisol/ui` ya compone — la misma que oye
 * quien usa móvil.
 *
 * `null` no es un hueco: es «con menos de tres ejercicios una línea no dice
 * nada», y se escribe, porque una celda en blanco se lee como «no calculable»
 * (regla 6 de honestidad).
 */
function TrendCell({ spark }: { spark: Sparkline | null | undefined }) {
  if (!spark) {
    return (
      <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }} title="serie corta">
        serie corta
      </span>
    );
  }
  const width = 40;
  const height = 14;
  const points = spark.points
    // El eje vertical del SVG crece hacia abajo; la serie, hacia arriba.
    .map((p) => `${(p.x * width).toFixed(1)},${((1 - p.y) * (height - 2) + 1).toFixed(1)}`)
    .join(' ');
  const stroke =
    spark.trend === 'up'
      ? colors.success
      : spark.trend === 'down'
        ? colors.danger
        : colors.textMuted;
  return (
    <svg width={width} height={height} role="img" aria-label={spark.ariaLabel}>
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={1.5} />
    </svg>
  );
}
