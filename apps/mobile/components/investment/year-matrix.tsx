import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Svg, { Polyline } from 'react-native-svg';

import { colors, fontSize, fontWeight, helpParagraphs, MARK, radius, spacing } from '@crisol/ui';
import type { MarkEntry, MatrixRow, Sparkline } from '@crisol/ui';

/**
 * Matriz concepto × ejercicio en RN — hermana de `YearMatrix` de web.
 *
 * Comparten el MODELO (`MatrixRow`, construido en `@crisol/ui`) y no el
 * renderizado, que es lo único genuinamente distinto entre una tabla HTML y
 * unas `View`. Así los dos informes no pueden discrepar en qué métrica sale, en
 * qué orden ni con qué banda: eso ya está decidido antes de llegar aquí.
 *
 * La tabla scrollea en horizontal DENTRO de su contenedor y la columna del
 * concepto queda fuera del scroll, fija: en un móvil, perder de vista de qué
 * fila es el número que estás leyendo es perder el número.
 *
 * **El motivo por celda es pulsable.** `MatrixCell.title` lleva el porqué de un
 * hueco, de una aproximación o de una vara que no aplica — y en web sale como
 * `title=`, que en táctil no existe: aquí no se pintaba NUNCA. Cuando una
 * métrica falla por motivos distintos en años distintos, el de la fila sólo
 * puede contar uno, así que el resto se perdía. Tocar la celda lo enseña debajo
 * de la tabla, que es el único afordance que queda sin ratón.
 */
export function YearMatrix({
  years,
  rows,
  verdictYear,
  firstColumnLabel = 'Concepto',
  legend,
  marksLegend,
  highlightKey,
}: {
  years: number[];
  rows: MatrixRow[];
  verdictYear?: number | undefined;
  firstColumnLabel?: string;
  legend?: string | undefined;
  /** Qué significa cada marca (PHASE-44.24.E). Derivada del registro único. */
  marksLegend?: readonly MarkEntry[] | undefined;
  /** Fila a la que se ha llegado desde el veredicto (PHASE-44.24). */
  highlightKey?: string | null | undefined;
}) {
  // PHASE-44.23 — el mismo panel sirve ahora para dos cosas: el motivo de una
  // CELDA (por qué falta ese año) y la definición de una FILA (qué es este
  // concepto). Se identifican por `id` en vez de por (etiqueta, año), porque la
  // definición no tiene año y comparar por etiqueta encendería dos filas
  // homónimas de bloques distintos.
  const [detail, setDetail] = useState<{ id: string; title: string; text: string } | null>(null);
  // PHASE-44.24.D — la columna existe si ALGUNA fila trae la clave, igual que
  // en web: cabecera y rellenos de grupo tienen que cuadrar con ella o las
  // columnas se desalinean en el scroll horizontal.
  const hasTrend = rows.some((row) => 'spark' in row);
  return (
    <View style={{ gap: spacing.sm }}>
      <View style={styles.table}>
        <View style={styles.labelColumn}>
          <Text style={[styles.headerCell, styles.labelHeader]} numberOfLines={2}>
            {firstColumnLabel}
          </Text>
          {rows.map((row) => {
            // PHASE-44.23 — la definición se abre TOCANDO la etiqueta. En táctil
            // no hay hover, así que un `title` como el de web no existiría; el
            // panel de abajo es el mismo que ya explicaba el motivo de una celda.
            const helpId = `help-${row.key}`;
            const helpOpen = detail?.id === helpId;
            const help = row.isGroup ? undefined : row.help;
            return (
              <Pressable
                key={row.key}
                disabled={!help}
                accessibilityRole={help ? 'button' : undefined}
                accessibilityLabel={help ? `Qué es «${row.label}»` : undefined}
                onPress={() =>
                  help
                    ? setDetail(
                        helpOpen
                          ? null
                          : {
                              id: helpId,
                              title: row.label,
                              // Mismo orden y mismos rótulos que en web
                              // (`helpParagraphs` es compartida); lo único
                              // propio de móvil es unirlos con saltos de
                              // línea en vez de pintar un párrafo por tramo.
                              text: helpParagraphs(row)
                                .map((part) =>
                                  part.label ? `${part.label}: ${part.text}` : part.text,
                                )
                                .join('\n\n'),
                            },
                      )
                    : undefined
                }
                style={[
                  row.isGroup ? styles.groupLabel : styles.labelCell,
                  highlightKey === row.key ? styles.highlighted : null,
                ]}
              >
                <Text
                  style={[
                    row.isGroup ? styles.groupText : rowLabelStyle(row.emphasis),
                    helpOpen || highlightKey === row.key ? styles.labelSelected : null,
                  ]}
                  numberOfLines={2}
                >
                  {row.label}
                  {help ? ' ⓘ' : ''}
                </Text>
                {row.hint && !row.isGroup ? (
                  <Text style={styles.hint} numberOfLines={1}>
                    {row.hint}
                  </Text>
                ) : null}
              </Pressable>
            );
          })}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator style={{ flex: 1 }}>
          <View>
            <View style={styles.row}>
              {years.map((year) => (
                <Text key={year} style={[styles.headerCell, styles.valueCell]}>
                  {year}
                  {year === verdictYear ? ` ${MARK.verdict_year.glyph}` : ''}
                </Text>
              ))}
              {hasTrend ? <Text style={[styles.headerCell, styles.valueCell]}>Tend.</Text> : null}
            </View>
            {rows.map((row) => (
              <View key={row.key} style={[styles.row, row.isGroup ? styles.groupRowSpacer : null]}>
                {row.isGroup
                  ? [...years, ...(hasTrend ? ['trend'] : [])].map((year) => (
                      <Text key={year} style={[styles.valueCell, styles.groupFiller]} />
                    ))
                  : row.cells.map((cell, i) => {
                      const year = years[i];
                      const cellId = `${row.key}-${year ?? i}`;
                      const selected = detail?.id === cellId;
                      return (
                        <Pressable
                          key={`${row.key}-${year ?? i}`}
                          disabled={!cell.title}
                          onPress={() =>
                            cell.title && year !== undefined
                              ? setDetail(
                                  selected
                                    ? null
                                    : {
                                        id: cellId,
                                        title: `${row.label} · ${year}`,
                                        text: cell.title,
                                      },
                                )
                              : undefined
                          }
                          style={[
                            styles.bodyCell,
                            cell.background ? { backgroundColor: cell.background } : null,
                            selected ? styles.cellSelected : null,
                          ]}
                        >
                          <Text
                            style={[
                              styles.valueCell,
                              { color: cell.color ?? colors.text },
                              row.emphasis ? { fontWeight: fontWeight.semibold } : null,
                              // El punto marca que hay algo que leer detrás.
                              cell.title ? styles.hasDetail : null,
                            ]}
                            numberOfLines={1}
                          >
                            {cell.text}
                            {cell.mark ?? ''}
                            {cell.title ? ' ·' : ''}
                          </Text>
                        </Pressable>
                      );
                    })}
                {/* Vacía en las filas sin serie, para que la rejilla no se
                    desalinee (misma regla que en web). */}
                {hasTrend && !row.isGroup ? (
                  <View style={styles.trendCell}>
                    {'spark' in row ? <TrendCell spark={row.spark} /> : null}
                  </View>
                ) : null}
              </View>
            ))}
          </View>
        </ScrollView>
      </View>
      {detail ? (
        <Pressable onPress={() => setDetail(null)} style={styles.detail}>
          <Text style={styles.detailTitle}>{detail.title}</Text>
          <Text style={styles.detailText}>{detail.text}</Text>
        </Pressable>
      ) : null}
      {legend ? <Text style={styles.legend}>{legend}</Text> : null}
      {marksLegend?.map((entry) => (
        <Text key={entry.glyph} style={styles.legend}>
          {entry.glyph} {entry.title}
        </Text>
      ))}
    </View>
  );
}

/** Alto fijo por fila: sin él las dos columnas (la fija y la que scrollea) se
 *  desalinean en cuanto una etiqueta ocupa dos líneas y otra una. */
const ROW_HEIGHT = 44;
const GROUP_HEIGHT = 32;
const HEADER_HEIGHT = 28;

function rowLabelStyle(emphasis: boolean | undefined) {
  return {
    color: emphasis ? colors.text : colors.textMuted,
    fontSize: fontSize.xs,
    fontWeight: emphasis ? fontWeight.semibold : fontWeight.regular,
  };
}

const styles = StyleSheet.create({
  trendCell: { justifyContent: 'center', alignItems: 'center', minWidth: 44 },
  highlighted: { backgroundColor: colors.primarySoft },
  trendEmpty: { color: colors.textSubtle, fontSize: 10 },
  table: { flexDirection: 'row' },
  labelColumn: {
    width: 132,
    borderRightWidth: 1,
    borderRightColor: colors.border,
    backgroundColor: colors.surface,
  },
  row: { flexDirection: 'row' },
  headerCell: {
    height: HEADER_HEIGHT,
    color: colors.textMuted,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    textAlign: 'right',
    paddingHorizontal: spacing.xs,
  },
  labelHeader: { textAlign: 'left' },
  labelCell: {
    height: ROW_HEIGHT,
    justifyContent: 'center',
    paddingHorizontal: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  groupLabel: { height: GROUP_HEIGHT, justifyContent: 'flex-end', paddingHorizontal: spacing.xs },
  groupRowSpacer: { height: GROUP_HEIGHT },
  groupFiller: { height: GROUP_HEIGHT, borderBottomWidth: 0 },
  groupText: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    textTransform: 'uppercase',
  },
  hint: { color: colors.textSubtle, fontSize: 10, marginTop: 1 },
  valueCell: {
    minWidth: 78,
    paddingHorizontal: spacing.xs,
    textAlign: 'right',
    fontSize: fontSize.xs,
  },
  bodyCell: {
    height: ROW_HEIGHT,
    justifyContent: 'center',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  cellSelected: { borderWidth: 1, borderColor: colors.primary },
  labelSelected: { color: colors.primary },
  hasDetail: { textDecorationLine: 'underline', textDecorationStyle: 'dotted' },
  detail: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    padding: spacing.sm,
    gap: 2,
  },
  detailTitle: { color: colors.text, fontSize: fontSize.xs, fontWeight: fontWeight.semibold },
  detailText: { color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 16 },
  legend: { color: colors.textSubtle, fontSize: 10, lineHeight: 15 },
});

/**
 * La serie de una fila, en RN (PHASE-44.24.D).
 *
 * Misma forma y mismos colores que en web, y la MISMA frase de accesibilidad —
 * la compone `@crisol/ui`, así que un lector de pantalla oye lo mismo en las dos
 * apps. `react-native-svg` es dependencia DIRECTA de la app
 * (`apps/mobile/package.json`), no una peer transitiva de gifted-charts: con el
 * linker aislado de pnpm, lo segundo no resolvería.
 */
function TrendCell({ spark }: { spark: Sparkline | null | undefined }) {
  // `null` no es «no hay datos»: es «con menos de tres puntos una línea no dice
  // nada». Dejar la celda en blanco se leería como «no calculable».
  if (!spark) return <Text style={styles.trendEmpty}>corta</Text>;
  const width = 36;
  const height = 12;
  const points = spark.points
    .map((point) => {
      const x = (point.x * width).toFixed(1);
      const y = ((1 - point.y) * (height - 2) + 1).toFixed(1);
      return `${x},${y}`;
    })
    .join(' ');
  const stroke =
    spark.trend === 'up'
      ? colors.success
      : spark.trend === 'down'
        ? colors.danger
        : colors.textMuted;
  return (
    <Svg width={width} height={height} accessibilityLabel={spark.ariaLabel}>
      <Polyline points={points} fill="none" stroke={stroke} strokeWidth={1.5} />
    </Svg>
  );
}
