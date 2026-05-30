import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  canStepNext,
  canStepPrev,
  clampAnchor,
  periodLabel,
  stepAnchor,
} from '@crisol/services';
import type { DebtTimeRange } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface PeriodNavigatorProps {
  range: DebtTimeRange;
  onRangeChange: (range: DebtTimeRange) => void;
  /** Mes ancla `YYYY-MM` del período mostrado. */
  anchor: string;
  onAnchorChange: (anchor: string) => void;
  availableFrom: string | null;
  availableTo: string | null;
}

const RANGE_LABEL: Record<DebtTimeRange, string> = {
  month: 'Mes',
  quarter: 'Trim.',
  year: 'Año',
};

const RANGES: DebtTimeRange[] = ['month', 'quarter', 'year'];

/**
 * PHASE-30.8 — Navegador de período (mobile parity del web): toggle de
 * granularidad (Mes / Trim. / Año) + flechas ◀ ▶ que recorren períodos
 * concretos, limitadas al rango con datos (`availableFrom`/`availableTo`).
 */
export function PeriodNavigator({
  range,
  onRangeChange,
  anchor,
  onAnchorChange,
  availableFrom,
  availableTo,
}: PeriodNavigatorProps) {
  const prevEnabled = canStepPrev(range, anchor, availableFrom);
  const nextEnabled = canStepNext(range, anchor, availableTo);

  function handleRange(next: DebtTimeRange) {
    onRangeChange(next);
    onAnchorChange(clampAnchor(next, anchor, availableFrom, availableTo));
  }

  function step(direction: 1 | -1) {
    onAnchorChange(
      clampAnchor(
        range,
        stepAnchor(range, anchor, direction),
        availableFrom,
        availableTo,
      ),
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.toggleRow}>
        {RANGES.map((opt) => (
          <Pressable
            key={opt}
            onPress={() => handleRange(opt)}
            style={[styles.toggleBtn, opt === range && styles.toggleBtnActive]}
            accessibilityRole="tab"
            accessibilityState={{ selected: opt === range }}
          >
            <Text
              style={[styles.toggleText, opt === range && styles.toggleTextActive]}
            >
              {RANGE_LABEL[opt]}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.navRow}>
        <Pressable
          onPress={() => step(-1)}
          disabled={!prevEnabled}
          style={[styles.arrow, !prevEnabled && styles.arrowDisabled]}
          accessibilityRole="button"
          accessibilityLabel="Período anterior"
        >
          <Text style={[styles.arrowText, !prevEnabled && styles.arrowTextDisabled]}>
            ‹
          </Text>
        </Pressable>
        <Text style={styles.label}>{periodLabel(range, anchor)}</Text>
        <Pressable
          onPress={() => step(1)}
          disabled={!nextEnabled}
          style={[styles.arrow, !nextEnabled && styles.arrowDisabled]}
          accessibilityRole="button"
          accessibilityLabel="Período siguiente"
        >
          <Text style={[styles.arrowText, !nextEnabled && styles.arrowTextDisabled]}>
            ›
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  toggleRow: {
    flexDirection: 'row',
    padding: 2,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toggleBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: radius.sm,
  },
  toggleBtnActive: {
    backgroundColor: colors.surface,
  },
  toggleText: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
  toggleTextActive: {
    color: colors.text,
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  arrow: {
    width: 32,
    height: 32,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrowDisabled: {
    opacity: 0.4,
  },
  arrowText: {
    fontSize: fontSize.lg,
    color: colors.text,
    lineHeight: fontSize.lg + 4,
  },
  arrowTextDisabled: {
    color: colors.textMuted,
  },
  label: {
    minWidth: 96,
    textAlign: 'center',
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
});
