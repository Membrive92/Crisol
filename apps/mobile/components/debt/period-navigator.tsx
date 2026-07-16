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

import { DateInput } from '../ui/date-input';

export interface PeriodNavigatorProps {
  range: DebtTimeRange;
  onRangeChange: (range: DebtTimeRange) => void;
  /** Mes ancla `YYYY-MM` del período mostrado. */
  anchor: string;
  onAnchorChange: (anchor: string) => void;
  availableFrom: string | null;
  availableTo: string | null;
  /**
   * PHASE-41 — expone la opción "Rango" (rango libre `from/to`). Off por
   * defecto: sólo donde el consumidor sabe manejar `range='custom'`.
   */
  allowCustom?: boolean;
  /** Rango libre activo (day-strings `YYYY-MM-DD`), sólo con `range='custom'`. */
  customFrom?: string | null;
  customTo?: string | null;
  onCustomRangeChange?: (from: string, to: string) => void;
}

const RANGE_LABEL: Record<DebtTimeRange, string> = {
  month: 'Mes',
  year: 'Año',
  custom: 'Rango',
};

/** Parsea un day-string `YYYY-MM-DD` a `Date` (UTC) para acotar los pickers. */
function toDate(day: string | null | undefined): Date | undefined {
  if (!day) return undefined;
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

/**
 * PHASE-30.8 / PHASE-41 — Navegador de período (mobile parity del web): toggle
 * de granularidad (Mes / Año / Rango) + flechas ◀ ▶ para los períodos
 * navegables, o dos date-pickers para el rango libre `custom`. Limitado al
 * rango con datos (`availableFrom`/`availableTo`).
 */
export function PeriodNavigator({
  range,
  onRangeChange,
  anchor,
  onAnchorChange,
  availableFrom,
  availableTo,
  allowCustom = false,
  customFrom = null,
  customTo = null,
  onCustomRangeChange,
}: PeriodNavigatorProps) {
  const ranges: DebtTimeRange[] = allowCustom
    ? ['month', 'year', 'custom']
    : ['month', 'year'];
  // PHASE-41 — `custom` no navega; los guards estrechan a `NavigableRange`.
  const prevEnabled = range !== 'custom' && canStepPrev(range, anchor, availableFrom);
  const nextEnabled = range !== 'custom' && canStepNext(range, anchor, availableTo);

  function handleRange(next: DebtTimeRange) {
    onRangeChange(next);
    if (next !== 'custom') {
      onAnchorChange(clampAnchor(next, anchor, availableFrom, availableTo));
    }
  }

  function step(direction: 1 | -1) {
    if (range === 'custom') return;
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
        {ranges.map((opt) => (
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

      {range === 'custom' ? (
        <View style={styles.customRow}>
          <DateInput
            value={customFrom ?? ''}
            maximumDate={toDate(customTo)}
            onChange={(from) => onCustomRangeChange?.(from, customTo ?? '')}
          />
          <Text style={styles.dash}>–</Text>
          <DateInput
            value={customTo ?? ''}
            minimumDate={toDate(customFrom)}
            onChange={(to) => onCustomRangeChange?.(customFrom ?? '', to)}
          />
        </View>
      ) : (
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
      )}
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
  customRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  dash: {
    color: colors.textMuted,
    fontSize: fontSize.sm,
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
