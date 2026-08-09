import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { MatrixRow } from '@crisol/ui';

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
}: {
  years: number[];
  rows: MatrixRow[];
  verdictYear?: number | undefined;
  firstColumnLabel?: string;
  legend?: string | undefined;
}) {
  const [detail, setDetail] = useState<{ label: string; year: number; text: string } | null>(null);
  return (
    <View style={{ gap: spacing.sm }}>
      <View style={styles.table}>
        <View style={styles.labelColumn}>
          <Text style={[styles.headerCell, styles.labelHeader]} numberOfLines={2}>
            {firstColumnLabel}
          </Text>
          {rows.map((row) => (
            <View key={row.key} style={row.isGroup ? styles.groupLabel : styles.labelCell}>
              <Text
                style={row.isGroup ? styles.groupText : rowLabelStyle(row.emphasis)}
                numberOfLines={2}
              >
                {row.label}
              </Text>
              {row.hint && !row.isGroup ? (
                <Text style={styles.hint} numberOfLines={2}>
                  {row.hint}
                </Text>
              ) : null}
            </View>
          ))}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator style={{ flex: 1 }}>
          <View>
            <View style={styles.row}>
              {years.map((year) => (
                <Text key={year} style={[styles.headerCell, styles.valueCell]}>
                  {year}
                  {year === verdictYear ? ' •' : ''}
                </Text>
              ))}
            </View>
            {rows.map((row) => (
              <View
                key={row.key}
                style={[styles.row, row.isGroup ? styles.groupRowSpacer : null]}
              >
                {row.isGroup
                  ? years.map((year) => (
                      <Text key={year} style={[styles.valueCell, styles.groupFiller]} />
                    ))
                  : row.cells.map((cell, i) => {
                      const year = years[i];
                      const selected =
                        detail !== null && detail.label === row.label && detail.year === year;
                      return (
                        <Pressable
                          key={`${row.key}-${year ?? i}`}
                          disabled={!cell.title}
                          onPress={() =>
                            cell.title && year !== undefined
                              ? setDetail(
                                  selected ? null : { label: row.label, year, text: cell.title },
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
              </View>
            ))}
          </View>
        </ScrollView>
      </View>
      {detail ? (
        <Pressable onPress={() => setDetail(null)} style={styles.detail}>
          <Text style={styles.detailTitle}>
            {detail.label} · {detail.year}
          </Text>
          <Text style={styles.detailText}>{detail.text}</Text>
        </Pressable>
      ) : null}
      {legend ? <Text style={styles.legend}>{legend}</Text> : null}
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
