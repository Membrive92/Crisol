import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { MonthOutlookResponse } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, radius, spacing } from '@crisol/ui';

export interface MonthOutlookCardProps {
  data: MonthOutlookResponse | undefined;
  currency: string;
}

/** Semáforo del runway (umbrales de fondo de emergencia, orientativos). */
function runwayTone(months: number): { color: string; label: string } {
  if (months < 3) return { color: colors.danger, label: 'ajustado' };
  if (months < 6) return { color: colors.warning, label: 'razonable' };
  return { color: colors.success, label: 'holgado' };
}

/**
 * PHASE-37.6 (parity 37.4) — Proyección de fin de mes: cuánto queda
 * comprometido este mes (gastos fijos + cuotas) y el colchón/runway. Lista de
 * cargos expandible. Equivalente RN de la card "Fin de mes" de web.
 */
export function MonthOutlookCard({ data, currency }: MonthOutlookCardProps) {
  const [expanded, setExpanded] = useState(false);
  const ref = data?.reference_currency ?? currency;
  const items = data?.committed_items ?? [];
  const runway = data?.runway_months ?? null;
  const tone = runway !== null ? runwayTone(runway) : null;

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Fin de mes</Text>
        {data ? (
          <Text style={styles.muted}>
            {data.days_remaining} {data.days_remaining === 1 ? 'día' : 'días'}
          </Text>
        ) : null}
      </View>

      <Text style={styles.label}>COMPROMETIDO RESTANTE</Text>
      <Text style={styles.value}>
        {data ? formatAmount(data.committed_remaining, ref) : '—'}
      </Text>
      <Text style={styles.subtle}>
        {items.length} {items.length === 1 ? 'cargo previsto' : 'cargos previstos'}
      </Text>

      <View style={styles.runwayRow}>
        <View style={[styles.dot, { backgroundColor: tone?.color ?? colors.textSubtle }]} />
        <Text style={styles.runwayText}>
          {runway !== null ? (
            <>
              Colchón:{' '}
              <Text style={styles.bold}>{runway > 99 ? '99+' : runway.toFixed(1)} meses</Text>{' '}
              de gasto estructural ({tone?.label})
            </>
          ) : (
            <Text style={styles.muted}>
              Colchón no disponible — sin gasto estructural o saldo líquido negativo.
            </Text>
          )}
        </Text>
      </View>

      {items.length > 0 ? (
        <>
          <Pressable onPress={() => setExpanded((v) => !v)} hitSlop={8}>
            <Text style={styles.link}>{expanded ? 'Ocultar' : 'Ver'} cargos previstos</Text>
          </Pressable>
          {expanded
            ? items.map((it, i) => (
                <View key={`${it.name}-${it.expected_date}-${i}`} style={styles.itemRow}>
                  <Text style={styles.itemDate}>{it.expected_date.slice(5)}</Text>
                  <Text style={styles.itemName} numberOfLines={1}>
                    {it.name}
                    {it.overdue ? <Text style={styles.overdue}>  ATRASADO</Text> : null}
                  </Text>
                  <Text style={styles.itemAmount}>{formatAmount(it.amount, ref)}</Text>
                </View>
              ))
            : null}
        </>
      ) : (
        <Text style={styles.muted}>Nada comprometido en lo que queda de mes.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: { fontSize: fontSize.md, fontWeight: fontWeight.semibold, color: colors.text },
  label: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
    color: colors.textMuted,
    letterSpacing: 0.5,
  },
  value: {
    fontSize: fontSize.xxl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    marginTop: spacing.xs,
  },
  subtle: { fontSize: fontSize.xs, color: colors.textSubtle, marginTop: 2 },
  runwayRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
    padding: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceMuted,
  },
  dot: { width: 8, height: 8, borderRadius: 999 },
  runwayText: { flex: 1, fontSize: fontSize.sm, color: colors.text },
  bold: { fontWeight: fontWeight.bold },
  muted: { fontSize: fontSize.sm, color: colors.textMuted },
  link: {
    marginTop: spacing.md,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
    color: colors.primary,
  },
  itemRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm },
  itemDate: { minWidth: 44, fontSize: fontSize.xs, color: colors.textMuted },
  itemName: { flex: 1, fontSize: fontSize.sm, color: colors.text },
  overdue: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold, color: colors.danger },
  itemAmount: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.text },
});
